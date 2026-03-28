from flask import Flask, render_template, request, jsonify
import hashlib, base64, time, re, json, random, string, os, uuid, threading, tempfile
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# ─── In-memory persistence ───────────────────────────────────────────────────
tasks = {}
gallery = []
tasks_lock = threading.Lock()
gallery_lock = threading.Lock()


# ─── TempMailClient ──────────────────────────────────────────────────────────

class FakeMailClient:
    BASE = "https://api.tempmail.lol"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        })
        self.email = None
        self.token = None
        self._seen_ids = set()

    def get_email(self):
        resp = self.session.get(f"{self.BASE}/generate")
        resp.raise_for_status()
        data = resp.json()
        self.email = data["address"]
        self.token = data["token"]
        return self.email

    def wait_for_code(self, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            resp = self.session.get(f"{self.BASE}/auth/{self.token}")
            resp.raise_for_status()
            data = resp.json()

            if data.get("token") == False:
                raise TimeoutError("Tempmail token süresi doldu!")

            emails = data.get("email") or []
            for mail in emails:
                mail_id = mail.get("id") or mail.get("from") or str(mail)
                if mail_id not in self._seen_ids:
                    self._seen_ids.add(mail_id)
                    body = mail.get("body", "") or ""
                    subject = mail.get("subject", "") or ""
                    full_text = subject + " " + body
                    match = re.search(r'\b(\d{4,8})\b', full_text)
                    if match:
                        return match.group(1)

            time.sleep(3)

        raise TimeoutError("Kod süresi doldu!")


# ─── WayinClient ─────────────────────────────────────────────────────────────

def generate_ticket(reason, email, timestamp):
    raw = reason + email + str(timestamp)
    md5_hex = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return base64.b64encode(md5_hex.encode("utf-8")).decode("utf-8")

def random_username(length=12):
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


class WayinClient:
    BASE_URL = "https://wayinvideo-api.wayin.ai"
    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "origin": "https://wayin.ai",
        "referer": "https://wayin.ai/wayinvideo/login?type=signup",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "x-platform": "web",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def send_verify_code(self, email, reason="SIGNUP"):
        timestamp = int(time.time() * 1000)
        ticket = generate_ticket(reason, email, timestamp)
        payload = {"email": email, "reason": reason, "timestamp": timestamp, "ticket": ticket}
        resp = self.session.post(f"{self.BASE_URL}/verify_code", json=payload)
        resp.raise_for_status()
        return resp.json()

    def signup(self, username, email, password, verify_code):
        password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        payload = {"username": username, "email": email, "password": password_md5, "verify_code": verify_code}
        self.session.headers.update({"uncertified-redirect": "0"})
        resp = self.session.post(f"{self.BASE_URL}/signup", json=payload)
        resp.raise_for_status()
        return resp.json()

    def upload_image(self, image_path):
        filename = os.path.basename(image_path)
        filesize = os.path.getsize(image_path)
        self.session.headers.update({"referer": "https://wayin.ai/wayinvideo/ai-video"})
        resp = self.session.post(
            f"{self.BASE_URL}/api/video/generate/upload",
            json={"name": filename, "size": filesize, "resource_type": "AI_VIDEO_IMAGE"}
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        upload_url = data["upload_url"]
        s3_url = data["s3_url"]
        identify = data["identify"]

        with open(image_path, "rb") as f:
            put_resp = requests.put(
                upload_url,
                data=f,
                headers={
                    "content-type": "image/jpeg",
                    "origin": "https://wayin.ai",
                    "referer": "https://wayin.ai/wayinvideo/ai-video",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
                }
            )
            put_resp.raise_for_status()

        self.session.headers.update({"disable-msg": "1"})
        refresh_resp = self.session.post(
            f"{self.BASE_URL}/api/external_file/refresh_url",
            json={"url": s3_url}
        )
        refresh_resp.raise_for_status()
        signed_url = refresh_resp.json()["data"]["url"]
        return {"identify": identify, "s3_url": s3_url, "signed_url": signed_url}

    def generate_video(self, signed_url, instruction="", model="bytedance/seedance-1.5-pro",
                       ratio="16:9", duration="12", resolution="720p",
                       generate_audio=True, camera_fixed=False, auto_prompt=False):
        payload = {
            "model": model,
            "model_config": {
                "ratio": ratio,
                "duration": duration,
                "resolution": resolution,
                "generateAudio": generate_audio,
                "camera_fixed": camera_fixed,
                "image": signed_url,
            },
            "instruction": instruction,
            "auto_prompt": auto_prompt,
        }
        self.session.headers.update({"referer": "https://wayin.ai/wayinvideo/ai-video"})
        resp = self.session.post(f"{self.BASE_URL}/api/video/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["data"]

    def poll_status(self, generate_id, task_id):
        self.session.headers.update({
            "disable-msg": "1",
            "referer": f"https://wayin.ai/wayinvideo/ai-video/{task_id}",
        })
        resp = self.session.get(
            f"{self.BASE_URL}/api/video/generate/status",
            params={"generate_id": generate_id}
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def get_video_content(self, generate_id, task_id, fid):
        self.session.headers.update({
            "content-type": "application/x-www-form-urlencoded",
            "disable-msg": "1",
            "referer": f"https://wayin.ai/wayinvideo/ai-video/{task_id}",
        })
        resp = self.session.post(
            f"{self.BASE_URL}/api/video/generate/content",
            params={"generate_id": generate_id, "fid": fid},
            data=""
        )
        resp.raise_for_status()
        return resp.json()["data"]


# ─── Background worker ───────────────────────────────────────────────────────

def run_video_job(job_id, image_path, instruction, model, ratio, duration,
                  resolution, generate_audio, camera_fixed, auto_prompt, password):
    def update(stage, msg, extra=None):
        with tasks_lock:
            tasks[job_id]["stage"] = stage
            tasks[job_id]["log"].append(msg)
            if extra:
                tasks[job_id].update(extra)

    try:
        update("mail", "📧 Geçici email alınıyor...")
        fake_mail = FakeMailClient()
        email = fake_mail.get_email()
        update("mail", f"📧 Email: {email}", {"email": email})

        update("code", "📨 Doğrulama kodu gönderiliyor...")
        wayin = WayinClient()
        wayin.send_verify_code(email, reason="SIGNUP")

        update("code", "⏳ Kod bekleniyor (max 60s)...")
        code = fake_mail.wait_for_code(timeout=60)
        update("signup", f"✅ Kod alındı: {code}")

        username = random_username()
        wayin.signup(username, email, password, code)
        update("upload", f"👤 Kayıt olundu: {username}", {"username": username})

        update("upload", "⬆️ Resim yükleniyor...")
        upload_result = wayin.upload_image(image_path)
        try:
            os.unlink(image_path)
        except:
            pass
        update("generating", "🎬 Video oluşturuluyor...", {"signed_url": upload_result["signed_url"]})

        video_task = wayin.generate_video(
            signed_url=upload_result["signed_url"],
            instruction=instruction,
            model=model,
            ratio=ratio,
            duration=duration,
            resolution=resolution,
            generate_audio=generate_audio,
            camera_fixed=camera_fixed,
            auto_prompt=auto_prompt,
        )
        generate_id = video_task["generate_id"]
        task_id = video_task["task_id"]
        update("polling", f"🔄 Video işleniyor... task_id: {task_id}", {"generate_id": generate_id, "task_id_wayin": task_id})

        start = time.time()
        while time.time() - start < 600:
            data = wayin.poll_status(generate_id, task_id)
            status = data["status"]
            update("polling", f"🔄 Status: {status}")
            with tasks_lock:
                tasks[job_id]["wayin_status"] = status

            if status == "DONE":
                fid = data["results"][0]["fid"]
                content = wayin.get_video_content(generate_id, task_id, fid)
                video_url = content["url"]
                update("done", f"✅ Tamamlandı!", {"video_url": video_url, "fid": fid})
                with tasks_lock:
                    tasks[job_id]["status"] = "done"

                with gallery_lock:
                    gallery.append({
                        "id": job_id,
                        "video_url": video_url,
                        "instruction": instruction,
                        "image_path": image_path,
                        "model": model,
                        "ratio": ratio,
                        "duration": duration,
                        "resolution": resolution,
                        "created_at": int(time.time()),
                    })
                return

            elif status == "FAILED":
                err = data.get("error_code", "unknown")
                update("error", f"❌ Hata: {err}")
                with tasks_lock:
                    tasks[job_id]["status"] = "error"
                return

            time.sleep(5)

        update("error", "⏰ Zaman aşımı!")
        with tasks_lock:
            tasks[job_id]["status"] = "error"

    except Exception as e:
        with tasks_lock:
            tasks[job_id]["status"] = "error"
            tasks[job_id]["log"].append(f"❌ Exception: {str(e)}")
            tasks[job_id]["stage"] = "error"


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def api_generate():
    if "image" not in request.files:
        return jsonify({"error": "Resim gerekli"}), 400

    file = request.files["image"]
    ext = os.path.splitext(file.filename)[1] or ".jpg"

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    file.save(tmp.name)
    tmp.close()
    image_path = tmp.name

    instruction    = request.form.get("instruction", "")
    ratio          = request.form.get("ratio", "16:9")
    generate_audio = request.form.get("generate_audio", "true") == "true"
    camera_fixed   = request.form.get("camera_fixed", "false") == "true"
    model          = "bytedance/seedance-1.5-pro"
    duration       = "12"
    resolution     = "720p"
    auto_prompt    = False
    password       = "Windows700@"

    job_id = uuid.uuid4().hex[:12]
    with tasks_lock:
        tasks[job_id] = {
            "id": job_id,
            "status": "running",
            "stage": "starting",
            "log": [],
            "instruction": instruction,
            "model": model,
            "video_url": None,
            "created_at": int(time.time()),
        }

    t = threading.Thread(
        target=run_video_job,
        args=(job_id, image_path, instruction, model, ratio, duration,
              resolution, generate_audio, camera_fixed, auto_prompt, password),
        daemon=True
    )
    t.start()

    def _cleanup():
        time.sleep(120)
        try:
            os.unlink(image_path)
        except:
            pass
    threading.Thread(target=_cleanup, daemon=True).start()

    return jsonify({"job_id": job_id})

@app.route("/api/task/delete/<job_id>", methods=["DELETE"])
def api_task_delete(job_id):
    with tasks_lock:
        tasks.pop(job_id, None)
    return jsonify({"ok": True})

@app.route("/api/tasks")
def api_tasks():
    with tasks_lock:
        return jsonify(list(tasks.values()))

@app.route("/api/task/<job_id>")
def api_task(job_id):
    with tasks_lock:
        t = tasks.get(job_id)
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify(t)

@app.route("/api/gallery")
def api_gallery():
    with gallery_lock:
        return jsonify(list(reversed(gallery)))

@app.route("/api/gallery/delete/<job_id>", methods=["DELETE"])
def api_gallery_delete(job_id):
    with gallery_lock:
        idx = next((i for i, g in enumerate(gallery) if g["id"] == job_id), None)
        if idx is not None:
            gallery.pop(idx)
    with tasks_lock:
        tasks.pop(job_id, None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
