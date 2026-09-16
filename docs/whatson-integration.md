# What’sOn integration findings

Repository: https://github.com/klill6506/whats-on
Reviewed public source on 2026-09-16; no upstream changes made.

- FastAPI application; deployed URL documented as https://whatson.kenlill.com.
- TMDB supplies posters and US streaming-provider information through the existing
  server-side TMDB_API_KEY integration. No IMDb API integration was found.
- Trakt supplies recommendations, related shows, and episode/air-date information.
- What’sOn stores viewing progress itself in its own SQLite/PostgreSQL database.
  Do not assume this is synchronized with a personal Trakt watch history.
- GET /api/shows exposes a read-only show list suitable for a BobTV adapter.
- Reuse What’sOn as the source of progress and existing artwork rather than copying
  credentials or creating a second tracking database on the MeLE.
- Preserve the existing categories and current_episode=99 caught-up sentinel.
- A read-only Continue Watching row is the first proposed integration. Linking a
  show to a service does not imply verified episode-specific playback links.
- Automatic approval review blocked a live show-list fetch pending explicit
  approval for personal viewing-history access. No live data fetched yet.

## Implemented after explicit approval

Ken approved live read-only access on 2026-09-16. The adapter in whatson.py now
feeds /api/continue. It filters hiatus and current_episode=99, preserves recorded
progress, maps known services, and leaves unmapped services disabled in the UI.
Poster clicks open service homepages; exact title/episode links remain future work.
