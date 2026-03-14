import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger("maintenance-eye.seeder")


def _read_seed_file_sync(seed_path: Path) -> dict | None:
    try:
        with open(seed_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read seed file at {seed_path}: {e}")
        return None


async def auto_seed_firestore(eam_service) -> None:
    """Auto-seed Firestore if collections are empty."""
    from services.firestore_eam import FirestoreEAM

    if not isinstance(eam_service, FirestoreEAM):
        return

    try:
        existing_assets = await eam_service.search_assets()
        if len(existing_assets) > 0:
            logger.info(f"Firestore has {len(existing_assets)} assets — skipping seed")
            return

        logger.warning("Firestore collections are empty — auto-seeding from seed_data.json")

        base_dir = Path(__file__).resolve().parent.parent
        seed_path = base_dir / "data" / "seed_data.json"
        if not seed_path.exists():
            seed_path = base_dir.parent / "data" / "seed_data.json"

        if not seed_path.exists():
            logger.error("seed_data.json not found — cannot auto-seed Firestore")
            return

        seed = await asyncio.to_thread(_read_seed_file_sync, seed_path)
        if not seed:
            return

        batch = eam_service.db.batch()
        count = 0
        for collection_name, items in seed.items():
            if not isinstance(items, list):
                continue
            id_fields = {
                "assets": "asset_id",
                "work_orders": "wo_id",
                "eam_codes": "code",
                "inspections": "inspection_id",
                "knowledge_base": "doc_id",
            }
            id_field = id_fields.get(collection_name)
            for item in items:
                doc_id = item.get(id_field, str(count)) if id_field else str(count)
                ref = eam_service.db.collection(collection_name).document(doc_id)
                batch.set(ref, item)
                count += 1
                if count % 400 == 0:
                    await batch.commit()
                    batch = eam_service.db.batch()

        if count % 400 != 0:
            await batch.commit()
        logger.info(f"Auto-seeded Firestore with {count} documents across {len(seed)} collections")

    except Exception as e:
        logger.warning(f"Auto-seed check failed (non-fatal): {e}")
