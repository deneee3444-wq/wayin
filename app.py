from flask import Flask, render_template, request, jsonify
import hashlib, base64, time, re, json, random, string, os, uuid, threading, tempfile
import requests

app = Flask(__name__)

# ─── In-memory persistence ───────────────────────────────────────────────────
tasks = {}
gallery = []
tasks_lock = threading.Lock()
gallery_lock = threading.Lock()


# ─── Model Kataloğu ──────────────────────────────────────────────────────────

VIDEO_TYPE_LABELS = {
    "txt2vid": "Metinden Videoya",
    "img2vid": "Görüntüden Videoya",
    "ref2vid": "Referans Görselden Videoya",
}

MODEL_CATALOG = {
    "txt2vid": {
        "Google": [
            {"name": "Veo 3.1 Lite",  "model": "veo-3.1-lite-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False},
            {"name": "Veo 3.1",       "model": "veo-3.1-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False},
            {"name": "Veo 3.1 Fast",  "model": "veo-3.1-fast-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False},
            {"name": "Veo 3.0",       "model": "veo-3.0-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False},
            {"name": "Veo 3.0 Fast",  "model": "veo-3.0-fast-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False},
            {"name": "Veo 2.0",       "model": "veo-2.0-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p"],         "durations": ["5","6","7","8"], "audio": False, "camera_fixed": False},
        ],
        "ByteDance": [
            {"name": "Seedance 1.5 Pro", "model": "bytedance/seedance-1.5-pro",      "ratios": ["16:9","9:16","1:1","21:9","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["4","8","12"], "audio": True,  "camera_fixed": False},
            {"name": "Seedance 1.0 Pro", "model": "bytedance/v1-pro-text-to-video",  "ratios": ["16:9","9:16","1:1","21:9","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],     "audio": False, "camera_fixed": True},
            {"name": "Seedance 1.0 Lite","model": "bytedance/v1-lite-text-to-video", "ratios": ["16:9","9:16","1:1","4:3","3:4"],         "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],     "audio": False, "camera_fixed": True},
        ],
        "OpenAI": [
            {"name": "Sora 2", "model": "sora-2", "ratios": ["16:9","9:16"], "resolutions": ["720p"], "durations": ["4","8","12"], "audio": False, "camera_fixed": False},
        ],
        "Wan": [
            {"name": "Wan 2.6",      "model": "wan2.6-t2v",        "ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["720p","1080p"],        "durations": ["5","10","15"], "audio": True,  "camera_fixed": False},
            {"name": "Wan 2.5",      "model": "wan2.5-t2v-preview","ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],      "audio": True,  "camera_fixed": False},
            {"name": "Wan 2.2 Plus", "model": "wan2.2-t2v-plus",   "ratios": ["16:9","9:16","1:1"],             "resolutions": ["480p","1080p"],         "durations": ["5"],           "audio": False, "camera_fixed": False},
        ],
        "Kling": [
            {"name": "Kling 3.0 Omni",     "model": "kling-v3-omni",                      "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10","12","15"], "audio": True,  "camera_fixed": False},
            {"name": "Kling 3.0",          "model": "kling-v3",                           "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10","12","15"], "audio": True,  "camera_fixed": False},
            {"name": "Kling O1",           "model": "kling-video-o1",                     "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["5","10"],                                   "audio": False, "camera_fixed": False},
            {"name": "Kling 2.5 Turbo Pro","model": "kling/v2-5-turbo-text-to-video-pro", "ratios": ["16:9","9:16","1:1"], "resolutions": ["1080p"],        "durations": ["5","10"],                                   "audio": False, "camera_fixed": False},
            {"name": "Kling 2.6",          "model": "kling-2.6/text-to-video",            "ratios": ["16:9","9:16","1:1"], "resolutions": ["1080p"],        "durations": ["5","10"],                                   "audio": True,  "camera_fixed": False},
        ],
    },
    "img2vid": {
        "Google": [
            {"name": "Veo 3.1 Lite", "model": "veo-3.1-lite-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Veo 3.1",      "model": "veo-3.1-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Veo 3.1 Fast", "model": "veo-3.1-fast-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Veo 3.0",      "model": "veo-3.0-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False, "last_frame": False},
            {"name": "Veo 3.0 Fast", "model": "veo-3.0-fast-generate-001",  "ratios": ["16:9","9:16"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"],    "audio": True,  "camera_fixed": False, "last_frame": False},
            {"name": "Veo 2.0",      "model": "veo-2.0-generate-001",       "ratios": ["16:9","9:16"], "resolutions": ["720p"],         "durations": ["5","6","7","8"], "audio": False, "camera_fixed": False, "last_frame": False},
        ],
        "ByteDance": [
            {"name": "Seedance 1.5 Pro",     "model": "bytedance/seedance-1.5-pro",           "ratios": ["16:9","9:16","1:1","21:9","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["4","8","12"], "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Seedance 1.0 Pro",     "model": "bytedance/v1-pro-image-to-video",      "ratios": ["16:9","9:16","1:1","21:9","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],     "audio": False, "camera_fixed": True,  "last_frame": False},
            {"name": "Seedance 1.0 Lite",    "model": "bytedance/v1-lite-image-to-video",     "ratios": ["16:9","9:16","1:1","4:3","3:4"],         "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],     "audio": False, "camera_fixed": True,  "last_frame": True},
            {"name": "Seedance 1.0 Pro Fast","model": "bytedance/v1-pro-fast-image-to-video", "ratios": ["16:9","9:16","1:1","4:3","3:4"],         "resolutions": ["720p","1080p"],         "durations": ["5","10"],     "audio": False, "camera_fixed": False, "last_frame": False},
        ],
        "OpenAI": [
            {"name": "Sora 2", "model": "sora-2", "ratios": ["16:9","9:16"], "resolutions": ["720p"], "durations": ["4","8","12"], "audio": False, "camera_fixed": False, "last_frame": False},
        ],
        "Wan": [
            {"name": "Wan 2.6",      "model": "wan2.6-i2v",        "ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["720p","1080p"],        "durations": ["5","10","15"], "audio": True,  "camera_fixed": False, "last_frame": False},
            {"name": "Wan 2.5",      "model": "wan2.5-i2v-preview","ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["480p","720p","1080p"], "durations": ["5","10"],      "audio": True,  "camera_fixed": False, "last_frame": False},
            {"name": "Wan 2.2 Plus", "model": "wan2.2-i2v-plus",   "ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["480p","1080p"],         "durations": ["5"],           "audio": False, "camera_fixed": False, "last_frame": False},
        ],
        "Kling": [
            {"name": "Kling 3.0 Omni",     "model": "kling-v3-omni",                        "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10","12","15"], "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Kling 3.0",          "model": "kling-v3",                             "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10","12","15"], "audio": True,  "camera_fixed": False, "last_frame": True},
            {"name": "Kling O1",           "model": "kling-video-o1",                       "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10"],           "audio": False, "camera_fixed": False, "last_frame": True},
            {"name": "Kling 2.5 Turbo Pro","model": "kling/v2-5-turbo-image-to-video-pro",  "ratios": ["16:9","9:16","1:1"], "resolutions": ["1080p"],        "durations": ["5","10"],                                   "audio": False, "camera_fixed": False, "last_frame": True},
            {"name": "Kling 2.6",          "model": "kling-2.6/image-to-video",             "ratios": ["16:9","9:16","1:1"], "resolutions": ["1080p"],        "durations": ["5","10"],                                   "audio": True,  "camera_fixed": False, "last_frame": False},
        ],
        "Runway": [
            {"name": "Gen-4 Turbo",  "model": "runway-gen4_turbo",  "ratios": ["16:9","9:16","1:1","4:3","3:4"], "resolutions": ["720p"], "durations": ["5","10"], "audio": False, "camera_fixed": False, "last_frame": False},
            {"name": "Gen-3A Turbo", "model": "runway-gen3a_turbo", "ratios": ["3:5","5:3"],                      "resolutions": ["720p"], "durations": ["5","10"], "audio": False, "camera_fixed": False, "last_frame": False},
        ],
    },
    "ref2vid": {
        "Google": [
            {"name": "Veo 3.1", "model": "veo-3.1-generate-001", "ratios": ["16:9"], "resolutions": ["720p","1080p"], "durations": ["4","6","8"], "audio": True,  "camera_fixed": False, "max_ref_images": 3},
        ],
        "Kling": [
            {"name": "Kling 3.0 Omni", "model": "kling-v3-omni",  "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10","12","15"], "audio": True,  "camera_fixed": False, "max_ref_images": 5},
            {"name": "Kling O1",        "model": "kling-video-o1", "ratios": ["16:9","9:16","1:1"], "resolutions": ["720p","1080p"], "durations": ["3","4","5","6","7","8","9","10"],           "audio": False, "camera_fixed": False, "max_ref_images": 5},
        ],
    },
}


def get_model_info(video_type, model_id):
    """MODEL_CATALOG'dan model bilgisini döner."""
    for group_models in MODEL_CATALOG.get(video_type, {}).values():
        for m in group_models:
            if m["model"] == model_id:
                return m
    return None


# ─── TempMailLolClient ───────────────────────────────────────────────────────

class TempMailLolClient:
    BASE = "https://api.tempmail.lol/v2"

    def __init__(self):
        self.email = None
        self.token = None
        self._seen_ids = set()

    def get_email(self):
        resp = requests.post(
            f"{self.BASE}/inbox/create",
            headers={"Content-Type": "application/json"},
            json={}
        )
        resp.raise_for_status()
        data = resp.json()
        self.email = data["address"]
        self.token = data["token"]
        return self.email

    def wait_for_code(self, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            resp = requests.get(
                f"{self.BASE}/inbox",
                params={"token": self.token}
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("expired"):
                raise TimeoutError("Posta kutusu süresi doldu!")

            for msg in data.get("emails", []):
                msg_id = msg.get("date")  # date as unique key
                if msg_id not in self._seen_ids:
                    self._seen_ids.add(msg_id)
                    body = msg.get("body", "") or ""
                    # Search in plain text body
                    match = re.search(r'\b(\d{4,8})\b', body)
                    if match:
                        return match.group(1)
                    # Also search in HTML if available
                    html = msg.get("html", "") or ""
                    match = re.search(r'\b(\d{4,8})\b', re.sub(r'<[^>]+>', ' ', html))
                    if match:
                        return match.group(1)
            time.sleep(2)
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

    def signup(self, username, email, password, verify_code, invitation_code=None):
        password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        payload = {"username": username, "email": email, "password": password_md5, "verify_code": verify_code}
        if invitation_code:
            payload["invitation_code"] = invitation_code
        self.session.headers.update({"uncertified-redirect": "0"})
        resp = self.session.post(f"{self.BASE_URL}/signup", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_user_info(self):
        self.session.headers.update({
            "disable-msg": "0",
            "referer": "https://wayin.ai/wayinvideo/settings/profile",
            "uncertified-redirect": "0",
        })
        resp = self.session.get(f"{self.BASE_URL}/api/user")
        resp.raise_for_status()
        return resp.json()["data"]

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

    def generate_video(self, model, model_config, instruction="", auto_prompt=False):
        payload = {
            "model": model,
            "model_config": model_config,
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

def register_one_account(password, invitation_code=None):
    """Tek hesap açar. WayinClient'i döner."""
    mail = TempMailLolClient()
    email = mail.get_email()
    wayin = WayinClient()
    wayin.send_verify_code(email, reason="SIGNUP")
    code = mail.wait_for_code(timeout=60)
    username = random_username()
    wayin.signup(username, email, password, code, invitation_code=invitation_code)
    return wayin, username, email


def run_video_job(job_id, instruction, model, model_config_base, auto_prompt, password,
                  video_type="img2vid", invite_mode=False,
                  image_path=None, last_frame_path=None, reference_paths=None):
    def update(stage, msg, extra=None):
        with tasks_lock:
            tasks[job_id]["stage"] = stage
            tasks[job_id]["log"].append(msg)
            if extra:
                tasks[job_id].update(extra)

    try:
        if invite_mode:
            update("mail", "📧 Ana hesap için email alınıyor...")
            main_wayin, main_user, main_email = register_one_account(password)
            update("signup", f"👤 Ana hesap açıldı: {main_email}", {"email": main_email, "username": main_user})

            update("signup", "🎫 Invite kodu alınıyor...")
            user_info = main_wayin.get_user_info()
            invitation_code = user_info.get("invitation_code")
            if not invitation_code:
                raise ValueError("Invite kodu alınamadı!")
            update("signup", f"🎫 Invite kodu: {invitation_code}", {"invitation_code": invitation_code})

            INVITE_COUNT = 5
            for i in range(1, INVITE_COUNT + 1):
                update("signup", f"👥 Alt hesap {i}/{INVITE_COUNT} açılıyor...")
                try:
                    register_one_account(password, invitation_code=invitation_code)
                    update("signup", f"✅ Alt hesap {i} açıldı")
                except Exception as e:
                    update("signup", f"⚠️ Alt hesap {i} başarısız: {e}")
            wayin = main_wayin
        else:
            update("mail", "📧 Geçici email alınıyor...")
            fake_mail = TempMailLolClient()
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

        # ── Görselleri yükle ve model_config oluştur ──
        model_config = dict(model_config_base)

        if video_type == "img2vid" and image_path:
            update("upload", "⬆️ Resim yükleniyor...")
            img_result = wayin.upload_image(image_path)
            try: os.unlink(image_path)
            except: pass
            model_config["image"] = img_result["signed_url"]

            if last_frame_path and os.path.exists(last_frame_path):
                update("upload", "⬆️ Son kare yükleniyor...")
                lf_result = wayin.upload_image(last_frame_path)
                try: os.unlink(last_frame_path)
                except: pass
                model_config["lastFrame"] = lf_result["signed_url"]

        elif video_type == "ref2vid" and reference_paths:
            ref_urls = []
            for i, path in enumerate(reference_paths, 1):
                update("upload", f"⬆️ Referans görsel {i}/{len(reference_paths)} yükleniyor...")
                r = wayin.upload_image(path)
                try: os.unlink(path)
                except: pass
                ref_urls.append(r["signed_url"])
            model_config["reference_images"] = ref_urls

        # ── Video oluştur ──
        update("generating", "🎬 Video oluşturuluyor...")
        video_task = wayin.generate_video(model, model_config, instruction, auto_prompt)
        generate_id  = video_task["generate_id"]
        task_id_wayin = video_task["task_id"]
        update("polling", f"🔄 Video işleniyor...", {"generate_id": generate_id, "task_id_wayin": task_id_wayin})

        # ── Poll ──
        start = time.time()
        while time.time() - start < 600:
            data   = wayin.poll_status(generate_id, task_id_wayin)
            status = data["status"]
            update("polling", f"🔄 Status: {status}")
            with tasks_lock:
                tasks[job_id]["wayin_status"] = status

            if status == "DONE":
                fid     = data["results"][0]["fid"]
                content = wayin.get_video_content(generate_id, task_id_wayin, fid)
                video_url = content["url"]
                update("done", "✅ Tamamlandı!", {"video_url": video_url, "fid": fid})
                with tasks_lock:
                    tasks[job_id]["status"] = "done"
                m_info = get_model_info(video_type, model)
                with gallery_lock:
                    gallery.append({
                        "id":         job_id,
                        "video_url":  video_url,
                        "instruction": instruction,
                        "model":      model,
                        "model_name": m_info["name"] if m_info else model,
                        "video_type": video_type,
                        "ratio":      model_config_base.get("ratio", "16:9"),
                        "duration":   model_config_base.get("duration", "?"),
                        "resolution": model_config_base.get("resolution", "?"),
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


@app.route("/api/models")
def api_models():
    return jsonify({"catalog": MODEL_CATALOG, "labels": VIDEO_TYPE_LABELS})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    video_type  = request.form.get("video_type", "img2vid")
    model       = request.form.get("model", "bytedance/seedance-1.5-pro")
    instruction = request.form.get("instruction", "")
    ratio       = request.form.get("ratio", "16:9")
    duration    = request.form.get("duration", "12")
    resolution  = request.form.get("resolution", "720p")
    invite_mode = request.form.get("invite_mode", "false") == "true"
    auto_prompt = False
    password    = "Windows700@"

    m_info = get_model_info(video_type, model)

    # Yalnızca modelin desteklediği parametreleri ekle
    model_config_base = {"ratio": ratio, "duration": duration, "resolution": resolution}
    if m_info and m_info.get("audio"):
        model_config_base["generateAudio"] = (request.form.get("generate_audio", "false") == "true")
    if m_info and m_info.get("camera_fixed"):
        model_config_base["camera_fixed"] = (request.form.get("camera_fixed", "false") == "true")

    # Dosya işlemleri
    image_path      = None
    last_frame_path = None
    reference_paths = []

    if video_type == "img2vid":
        if "image" not in request.files or not request.files["image"].filename:
            return jsonify({"error": "Resim gerekli"}), 400
        f   = request.files["image"]
        ext = os.path.splitext(f.filename)[1] or ".jpg"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        f.save(tmp.name); tmp.close()
        image_path = tmp.name

        if "last_frame" in request.files and request.files["last_frame"].filename:
            lf     = request.files["last_frame"]
            lf_ext = os.path.splitext(lf.filename)[1] or ".jpg"
            lf_tmp = tempfile.NamedTemporaryFile(suffix=lf_ext, delete=False)
            lf.save(lf_tmp.name); lf_tmp.close()
            last_frame_path = lf_tmp.name

    elif video_type == "ref2vid":
        ref_files = request.files.getlist("ref_images")
        if not any(rf.filename for rf in ref_files):
            return jsonify({"error": "En az 1 referans görsel gerekli"}), 400
        for rf in ref_files:
            if rf.filename:
                ext = os.path.splitext(rf.filename)[1] or ".jpg"
                tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                rf.save(tmp.name); tmp.close()
                reference_paths.append(tmp.name)

    job_id = uuid.uuid4().hex[:12]
    with tasks_lock:
        tasks[job_id] = {
            "id":          job_id,
            "status":      "running",
            "stage":       "starting",
            "log":         [],
            "instruction": instruction,
            "model":       model,
            "model_name":  m_info["name"] if m_info else model,
            "video_type":  video_type,
            "video_url":   None,
            "created_at":  int(time.time()),
        }

    t = threading.Thread(
        target=run_video_job,
        args=(job_id, instruction, model, model_config_base, auto_prompt, password),
        kwargs={
            "video_type":       video_type,
            "invite_mode":      invite_mode,
            "image_path":       image_path,
            "last_frame_path":  last_frame_path,
            "reference_paths":  reference_paths,
        },
        daemon=True
    )
    t.start()
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
