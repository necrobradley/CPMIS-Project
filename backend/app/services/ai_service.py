"""
AI Service - AI CPMIS
Semua interaksi AI lintas provider ada di sini.
"""
import json
import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
from openai import AsyncOpenAI
from pypdf import PdfReader
from app.core.config import settings
from app.services import ai_provider_routing
from app.services import mlapi_provider
from app.services.secure_ai_gateway import secure_ai_gateway

logger = logging.getLogger(__name__)


class AIService:
    @classmethod
    def _normalize_provider(cls, provider: Optional[str]) -> str:
        return ai_provider_routing.normalize_provider(provider)

    @classmethod
    def _route_provider(cls, route: str = "default") -> str:
        return ai_provider_routing.route_provider(route)

    @classmethod
    def _route_config(
        cls,
        route: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        return ai_provider_routing.route_config(
            route,
            provider_override=provider,
            model_override=model,
        )

    @classmethod
    def is_configured(cls, route: str = "default") -> bool:
        return ai_provider_routing.is_configured(route)

    @classmethod
    def local_status(cls) -> dict:
        return ai_provider_routing.local_status()

    async def _chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        route: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Helper: panggil chat completion dari provider OpenAI-compatible."""
        config = self._route_config(route, provider=provider, model=model)
        if not config["api_key"]:
            raise ValueError(
                f"API key AI belum dikonfigurasi untuk provider {config['provider']} "
                f"pada route {route}."
            )
        decision = secure_ai_gateway.prepare(system_prompt, user_message, route=route)
        if not decision.allowed:
            raise ValueError(decision.reason or "Secure AI Gateway memblokir request AI eksternal.")
        logger.info(
            "Secure AI Gateway route=%s provider=%s policy=%s sensitivity=%s categories=%s masked=%s original_chars=%s outbound_chars=%s",
            route,
            config["provider"],
            decision.policy,
            decision.sensitivity,
            ",".join(decision.categories) or "none",
            len(decision.replacements),
            decision.original_chars,
            decision.outbound_chars,
        )
        if config.get("driver") == "mlapi":
            result = await mlapi_provider.chat_completion(
                url=config["base_url"],
                api_key=config["api_key"],
                model=config.get("request_model") or config["model"],
                system_prompt=decision.system_prompt,
                user_message=decision.user_message,
                temperature=settings.AI_TEMPERATURE,
                max_tokens=config["max_tokens"],
                timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                payload_style=config.get("payload_style") or "messages",
                include_model=bool(config.get("include_model")),
                extra_payload_json=config.get("extra_payload_json") or "",
            )
            return secure_ai_gateway.restore(result, decision)

        client_kwargs = {
            "api_key": config["api_key"],
            "timeout": settings.AI_TIMEOUT_SECONDS,
        }
        if config["base_url"]:
            client_kwargs["base_url"] = config["base_url"]
        client = AsyncOpenAI(**client_kwargs)
        response = await client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": decision.system_prompt},
                {"role": "user", "content": decision.user_message},
            ],
            temperature=settings.AI_TEMPERATURE,
            max_tokens=config["max_tokens"],
        )
        return secure_ai_gateway.restore(response.choices[0].message.content, decision)

    # -----------------------------------------------------------------------------
    # DOCUMENT ANALYSIS
    # -----------------------------------------------------------------------------

    async def analyze_document(self, content: bytes, filename: str, doc_type: str) -> dict:
        """
        Analisis dokumen konstruksi (tender/kontrak).
        Ekstrak: scope, milestone, nilai, timeline, risiko.
        """
        text = self._extract_document_text(content, filename)[:16000]
        if not text.strip():
            raise ValueError("Dokumen tidak memiliki teks yang dapat dibaca; gunakan PDF/DOCX berbasis teks")

        system_prompt = """Kamu adalah AI ahli konstruksi bangunan di Indonesia.
Analisis dokumen konstruksi dan ekstrak informasi penting.
Selalu jawab dalam format JSON yang valid tanpa markdown.
"""
        user_message = f"""
Dokumen: {filename} (Tipe: {doc_type})
Isi dokumen:
{text}

Ekstrak dan kembalikan JSON dengan format:
{{
  "project_name": "nama proyek",
  "location": "lokasi proyek",
  "contract_value": 0,
  "start_date": "YYYY-MM-DD atau null",
  "end_date": "YYYY-MM-DD atau null",
  "scope_of_work": ["pekerjaan 1", "pekerjaan 2"],
  "milestones": [{{"name": "nama", "date": "YYYY-MM-DD", "description": "deskripsi"}}],
  "key_requirements": ["syarat 1", "syarat 2"],
  "material_specifications": [{{
    "related_scope": "pekerjaan/WBS terkait",
    "material_code": "kode material atau null",
    "material_name": "nama material",
    "technical_specification": "spesifikasi teknis",
    "standard_reference": "SNI/ASTM/IEC/dll atau null",
    "grade": "mutu/kelas atau null",
    "approved_manufacturer": "merek/produsen atau null",
    "dimensions": "ukuran atau null",
    "unit": "satuan atau null",
    "planned_quantity": null,
    "certificate_required": false,
    "test_required": false,
    "approval_required": true,
    "source_page": "nomor halaman atau null",
    "revision": "kode revisi atau null"
  }}],
  "risks": ["risiko 1", "risiko 2"],
  "divisions_needed": ["Struktur", "Arsitektur", "MEP", "dll"]
}}
Jangan mengarang spesifikasi material. Isi hanya data yang tertulis atau didukung kuat oleh dokumen dan pertahankan referensi halaman/revisi bila tersedia.
"""
        raw = await self._chat_completion(system_prompt, user_message, route="analysis")
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            # Fallback: kembalikan sebagai teks biasa
            return {"raw_analysis": raw, "error": "JSON parse failed"}

    @staticmethod
    def _extract_document_text(content: bytes, filename: str) -> str:
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if suffix == "pdf":
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == "docx":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml_content = archive.read("word/document.xml")
            root = ET.fromstring(xml_content)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            return " ".join(
                node.text or "" for node in root.iter(namespace + "t")
            )
        return content.decode("utf-8", errors="ignore")

    # -----------------------------------------------------------------------------
    # TASK GENERATION
    # -----------------------------------------------------------------------------

    async def generate_tasks(
        self,
        analysis: dict,
        project_id: int,
        available_roles: Optional[list[dict]] = None,
    ) -> list:
        """
        Dari hasil analisis dokumen -> generate task breakdown.
        Output: list of task dict.
        """
        system_prompt = """Kamu adalah project manager konstruksi berpengalaman di Indonesia.
Buat breakdown task yang terstruktur berdasarkan scope pekerjaan.
Selalu jawab dalam format JSON array yang valid tanpa markdown.
"""
        role_catalog = [
            {
                "code": role.get("code"),
                "label": role.get("label"),
                "responsibility": role.get("responsibility"),
            }
            for role in (available_roles or [])
            if role.get("code")
        ]
        role_instruction = (
            "Pilih tepat satu project_role dari katalog anggota aktif berikut untuk setiap task:\n"
            f"{json.dumps(role_catalog, ensure_ascii=False)}"
            if role_catalog
            else "Isi project_role dengan kode role proyek yang paling bertanggung jawab."
        )
        user_message = f"""
Berdasarkan analisis proyek ini:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

{role_instruction}

Buat daftar task yang perlu dikerjakan. Format JSON array:
[
  {{
    "wbs_code": "1.1.1",
    "parent_wbs": "1.1 atau null",
    "title": "Judul task",
    "description": "Deskripsi detail task",
    "priority": "low|medium|high|critical",
    "division": "nama divisi",
    "project_role": "kode role proyek PIC dari katalog anggota aktif",
    "deadline": "YYYY-MM-DD atau null",
    "estimated_days": 5,
    "acceptance_criteria": "kriteria terukur agar pekerjaan diterima",
    "reporting_instructions": "data lapangan yang wajib dilaporkan",
    "required_photo_count": 2,
    "required_document_count": 0,
    "requirements": [
      {{"code": "QUALITY", "title": "Pemeriksaan mutu", "description": "detail checklist"}}
    ],
    "materials": [
      {{
        "material_code": "MAT-001",
        "material_name": "Nama material",
        "category": "Beton/Baja/Finishing/MEP/dll",
        "technical_specification": "spesifikasi teknis lengkap dari dokumen",
        "standard_reference": "SNI/ASTM/IEC atau standar lain",
        "grade": "mutu atau kelas material",
        "approved_manufacturer": "merek/produsen yang disetujui atau null",
        "dimensions": "ukuran/ketebalan/diameter atau null",
        "unit": "m3/kg/unit/m2/dll",
        "planned_quantity": null,
        "certificate_required": true,
        "test_required": true,
        "approval_required": true,
        "source_page": "nomor halaman dokumen",
        "revision": "kode revisi"
      }}
    ]
  }}
]

Buat minimal 10 task yang realistis, memiliki hierarki WBS, dan terstruktur per divisi.
Jika katalog role aktif tersedia, buat cakupan kerja yang relevan bagi setiap role aktif. Jangan memberi task PIC kepada role di luar katalog.
Ekstrak material hanya jika disebut atau dapat diturunkan secara kuat dari dokumen. Jangan mengarang merek, standar, grade, kuantitas, atau sumber halaman.
Petakan setiap item pada material_specifications ke task/WBS terkait dan salin ke array materials task tersebut.
"""
        raw = await self._chat_completion(system_prompt, user_message, route="analysis")
        try:
            cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return []

    # -----------------------------------------------------------------------------
    # REPORT SUMMARIZATION
    # -----------------------------------------------------------------------------

    async def summarize_report(
        self,
        report_text: str,
        issues: str = "",
        work_progress: str = ""
    ) -> dict:
        """
        Ringkas laporan harian dan deteksi risiko.
        """
        system_prompt = """Kamu adalah supervisor konstruksi yang menganalisis laporan harian.
Berikan ringkasan singkat dan identifikasi risiko. Jawab dalam JSON.
"""
        user_message = f"""
Laporan Harian:
{report_text}

Progress Pekerjaan: {work_progress}
Masalah/Kendala: {issues}

Kembalikan JSON:
{{
  "summary": "ringkasan 2-3 kalimat",
  "risks": "daftar risiko yang terdeteksi",
  "recommendations": "saran tindak lanjut",
  "severity": "low|medium|high"
}}
"""
        raw = await self._chat_completion(system_prompt, user_message)
        try:
            cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"summary": raw, "risks": "", "recommendations": "", "severity": "low"}

    # -----------------------------------------------------------------------------
    # FREE CHAT
    # -----------------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        context: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Chat bebas dengan AI tentang proyek konstruksi."""
        system_prompt = f"""Kamu adalah asisten AI untuk manajemen proyek konstruksi di Indonesia.
Kamu membantu project manager, supervisor, dan staf lapangan.
Gunakan bahasa Indonesia yang profesional namun mudah dipahami.
{f"Konteks proyek saat ini: {context}" if context else ""}
"""
        return await self._chat_completion(
            system_prompt,
            message,
            provider=provider,
            model=model,
        )

    # -----------------------------------------------------------------------------
    # TELEGRAM MESSAGE PARSING
    # -----------------------------------------------------------------------------

    async def parse_telegram_report(self, message: str, user_name: str) -> dict:
        """
        Parse laporan harian yang dikirim via Telegram.
        Ekstrak: cuaca, jumlah pekerja, pekerjaan selesai, kendala.
        """
        system_prompt = """Kamu adalah parser laporan lapangan konstruksi.
Ekstrak informasi dari pesan Telegram laporan harian. Jawab dalam JSON.
"""
        user_message = f"""
Pesan dari {user_name}:
{message}

Ekstrak ke JSON:
{{
  "weather": "cuaca atau null",
  "manpower_count": 0,
  "work_progress": "apa yang dikerjakan",
  "issues": "kendala atau null",
  "actual_quantity": 0,
  "actual_unit": "m2/m3/m/unit/kg atau null",
  "actual_cost": 0,
  "report_text": "teks lengkap laporan yang sudah diformat rapi"
}}
"""
        raw = await self._chat_completion(system_prompt, user_message)
        try:
            cleaned = raw.strip().lstrip("```json").rstrip("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "weather": None,
                "manpower_count": 0,
                "work_progress": message,
                "issues": None,
                "actual_quantity": None,
                "actual_unit": None,
                "actual_cost": None,
                "report_text": message
            }
