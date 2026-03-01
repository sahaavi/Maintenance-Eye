# Next Session — Maintenance-Eye

**Last updated:** 2026-03-01
**Last session:** Enterprise Data Explorer Redesign

---

## Where We Left Off

The enterprise dashboard redesign is fully implemented and verified working via API tests locally. All changes are committed to `main`. The deployment to GCP Cloud Run has NOT been done since this session.

**What was completed this session:**
- Backend: `search_work_orders()` + `get_locations()` added to EAMService, JsonEAM, FirestoreEAM
- Backend: `GET /api/work-orders` now supports `q`, `priority`, `department`, `location`, `limit` filters
- Backend: `GET /api/locations` new endpoint
- Frontend: Single-tab dashboard replaced with 5-page enterprise explorer
- Frontend: Sidebar nav (desktop), bottom nav (mobile), filter bars per page, debounced search
- Frontend: SW cache v3, HTML params v4

---

## What to Work On Next

### Priority 1 — Deploy and Verify on Mobile (REQUIRED before hackathon)

```bash
./scripts/deploy.sh maintenance-eye-488403 <GEMINI_API_KEY> us-central1
```

After deploy, test on actual mobile device (Android Chrome or iOS Safari):
- [ ] Splash screen loads, camera/mic permissions requested
- [ ] Can connect to inspection session and speak to Max
- [ ] Dashboard navigation works on mobile (bottom nav)
- [ ] Work Orders filter bar works on mobile
- [ ] Confirmation card appears when Max proposes a work order

### Priority 2 — Run RULES.md Section 4 Verification Checklist

The full end-to-end checklist from `RULES.md` has never been completed. Go through it and check off each item.

### Priority 3 — Address Open Items from todo.md

- Load testing with concurrent sessions
- Test on iOS Safari specifically (PWA quirks)
- Review error handling coverage across all 8 agent tools
- Cloud Run logging verification

### Priority 4 — Bug Report Cleanup

Check `BUG_REPORT.md` — some bugs marked as fixed may need production verification. Use:
```bash
python3 scripts/manage_bugs.py update <id> --status "Verified Fixed"
```

---

## Important Reminders

1. **Cache busting:** SW is at v3, HTML params at v4. If any frontend file changes next session, bump to v4/v5 respectively.
2. **EAM interface:** When adding new methods, always update abstract base (`eam_interface.py`), then `json_eam.py`, then `firestore_eam.py`.
3. **RULES.md compliance:** Write plan to `tasks/todo.md` before any medium/high-risk work. Update `tasks/lessons.md` after.
4. **WSL2 limitation:** Camera/mic won't work in local dev — can test API and dashboard but not live inspection flow.
5. **Model name:** `gemini-2.5-flash-native-audio-latest` — the `-latest` suffix is required.

---

## Key File Paths

| Purpose | Path |
|---|---|
| Agent definition | `backend/agent/maintenance_agent.py` |
| Agent tools | `backend/agent/tools/` |
| REST routes | `backend/api/routes.py` |
| WebSocket handler | `backend/api/websocket.py` |
| EAM abstract interface | `backend/services/eam_interface.py` |
| JSON fallback EAM | `backend/services/json_eam.py` |
| Firestore EAM | `backend/services/firestore_eam.py` |
| Frontend app | `frontend/app.js` |
| Frontend HTML | `frontend/index.html` |
| Frontend styles | `frontend/style.css` |
| Service worker | `frontend/sw.js` |
| Task log | `tasks/todo.md` |
| Lessons | `tasks/lessons.md` |
| Bug report | `BUG_REPORT.md` |
