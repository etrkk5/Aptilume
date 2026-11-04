import hashlib
import json
import os
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from .models import Export, Publication
from .store import get
from .reporting import metrics
from .access import export_snapshot

MAX_EXPORT_SIZE = 50 * 1024 * 1024
EXPORT_DISK_BUDGET = 1024 * 1024 * 1024


def artifact_path(store, export, verify=True):
    directory = (store.settings.data_dir / "exports").resolve()
    candidate = Path(export.file or "")
    if (
        not directory.is_relative_to(store.settings.data_dir)
        or candidate.name != export.id + ".xlsx"
        or candidate.parent.resolve() != directory
        or candidate.is_symlink()
        or not candidate.is_file()
    ):
        from .store import DomainError

        raise DomainError(
            "invalid_artifact", "Excel dosyası bulunamadı veya geçersiz.", 409
        )
    if candidate.stat().st_size > MAX_EXPORT_SIZE:
        from .store import DomainError

        raise DomainError("invalid_artifact", "Excel dosya boyutu geçersiz.", 409)
    if verify and hashlib.sha256(candidate.read_bytes()).hexdigest() != export.sha256:
        from .store import DomainError

        raise DomainError(
            "artifact_integrity_failed",
            "Excel bütünlük kontrolü başarısız. Yeni çıktı oluşturun.",
            409,
        )
    return candidate


def add_sheet(wb, name, columns, rows):
    ws = wb.create_sheet(name)
    ws.append([label for _, label in columns])
    for row in rows:
        values = [row.get(k) for k, _ in columns]
        ws.append(
            [
                json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                for v in values
            ]
        )
        for cell, value in zip(ws[ws.max_row], values):
            if isinstance(value, (str, dict, list)):
                cell.data_type = "s"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="004587")
        cell.font = Font(color="FFFFFF", bold=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            65, max(18, len(str(col[0].value)) + 4)
        )
    return ws


def build_export(store, eid):
    with store.session() as s:
        export = get(s, Export, eid)
        pub = get(s, Publication, export.publication_id)
        snapshot = export_snapshot(store, s, export)
        filters = export.filters
        detailed = export.detail
        if export.status == "ready" and export.file:
            artifact_path(store, export)
            return
    report = metrics(snapshot, filters.get("team_id"), filters.get("skill_id"))
    wb = Workbook()
    wb.remove(wb.active)
    summary = [
        {"metric": k, "value": v}
        for k, v in report.items()
        if k
        in [
            "publication_id",
            "campaign_name",
            "run_id",
            "mock",
            "assigned",
            "submitted",
            "completion_rate",
            "common_score",
            "common_n",
            "level_coverage",
            "target_met_rate",
        ]
    ]
    add_sheet(wb, "Ozet", [("metric", "Metrik"), ("value", "Değer")], summary)
    add_sheet(
        wb,
        "Ekip_Yetkinlik",
        [
            ("team_name", "Ekip"),
            ("skill_name", "Yetkinlik"),
            ("n", "Geçerli kişi"),
            ("written_score", "Yazılı puan"),
            ("target_level", "Hedef seviye"),
            ("mean_gap", "Ortalama fark"),
            ("suppressed", "Küçük grup bastırıldı"),
        ],
        report["aggregates"],
    )
    if detailed:
        add_sheet(
            wb,
            "Kisi_Yetkinlik",
            [
                (k, label)
                for k, label in [
                    ("participant_id", "Kişi ID"),
                    ("name", "Ad"),
                    ("team_name", "Ekip"),
                    ("skill_name", "Yetkinlik"),
                    ("written_score", "Yazılı puan"),
                    ("mcq_score", "MCQ puanı"),
                    ("self_level", "Öz beyan"),
                    ("suggested_level", "Önerilen seviye"),
                    ("validated_level", "Doğrulanmış seviye"),
                    ("target_level", "Hedef"),
                    ("gap", "Hedef farkı"),
                    ("status", "Durum"),
                ]
            ],
            report["rows"],
        )
        allowed = {(r["assignment_id"], r["skill_id"]) for r in report["rows"]}
        answers = [
            a
            for a in snapshot["answers"]
            if (a["assignment_id"], a["skill_id"]) in allowed
        ]
        ids = {a["answer_id"] for a in answers}
        add_sheet(
            wb,
            "Yanitlar",
            [
                ("answer_id", "Yanıt ID"),
                ("participant_id", "Kişi ID"),
                ("question_type", "Tür"),
                ("question", "Soru"),
                ("text", "Yanıt metni"),
                ("selected", "Seçenekler"),
                ("submitted_at", "Gönderim zamanı"),
            ],
            answers,
        )
        add_sheet(
            wb,
            "Rubrik_Puanlari",
            [
                ("answer_id", "Yanıt ID"),
                ("criterion_id", "Kriter"),
                ("points", "Puan"),
                ("max_points", "Azami puan"),
                ("quotes", "Yanıttan alıntı"),
                ("reason", "Gerekçe"),
                ("override_score", "Düzeltme puanı"),
                ("review_reason", "İnceleme gerekçesi"),
            ],
            [r for r in snapshot["rubric_scores"] if r["answer_id"] in ids],
        )
    add_sheet(
        wb,
        "Gelistirme_Onerileri",
        [("action", "Gelişim aksiyonu")],
        [{"action": x} for x in snapshot.get("insights", {}).get("actions", [])],
    )
    add_sheet(
        wb,
        "Metodoloji",
        [("rule", "Kural"), ("value", "Açıklama")],
        [
            {"rule": "Sonuç sürümü", "value": pub.id},
            {"rule": "Filtreler", "value": filters},
            {
                "rule": "Skor",
                "value": "Yazılı rubrik puanı, MCQ ve öz beyan ayrı tutulur. Eksik/teknik hata sıfır değildir.",
            },
            {
                "rule": "Seviye",
                "value": "Anket önerisi; L4/L5 ve kurumsal etki doğrulanmış sayılmaz.",
            },
            {"rule": "Mock", "value": bool(snapshot["mock"])},
            {
                "rule": "Özet kapsamı",
                "value": "5 kişiden küçük toplu hücreler bastırılır. Kişisel açık yanıtlar yalnızca detaylı export'ta yer alır.",
            },
        ],
    )
    out = store.settings.data_dir / "exports"
    out.mkdir(exist_ok=True)
    if not out.resolve().is_relative_to(store.settings.data_dir):
        from .store import DomainError

        raise DomainError("invalid_path", "Çıktı dizini geçersiz.")
    if (
        sum(
            p.stat().st_size
            for p in out.glob("*.xlsx")
            if p.is_file() and not p.is_symlink()
        )
        >= EXPORT_DISK_BUDGET
    ):
        from .store import DomainError

        raise DomainError(
            "export_disk_limit",
            "Excel alanı dolu. Süresi dolan çıktıları temizleyin.",
            507,
        )
    temp = out / f"{eid}.tmp.xlsx"
    final = out / f"{eid}.xlsx"
    wb.save(temp)
    if temp.stat().st_size > MAX_EXPORT_SIZE:
        temp.unlink()
        from .store import DomainError

        raise DomainError(
            "export_size_limit",
            "Excel boyutu 50 MiB sınırını aşıyor. Kapsamı daraltın.",
        )
    os.replace(temp, final)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    with store.session() as s:
        e = get(s, Export, eid)
        e.status = "ready"
        e.file = str(final)
        e.sha256 = digest
