# Birthday Photo Wall

A web page projected on a wall at a party. Guests add photos to a Google Photos shared album; within a couple of
minutes each photo floats across the wall in a polaroid frame, and photos with faces get a fun effect (glasses,
mustache, party hat or vintage). The wall sits behind a passcode.

- `backend/`: FastAPI + a CLI (`python -m wall`) over one service: album sync, face detection (MediaPipe), effects.
- `frontend/`: Vite + React kiosk page (see `frontend/README.md`).
- `docs/DEPLOY.md`: running it as a container on a server, published through Tailscale Funnel.
- `docs/DESIGN.md`: the design; `mockup/wall-sample.html`: the visual reference.

## Run locally

```sh
cp config.example.yaml config.yaml    # set your album link and title
cp .env.example .env                  # set PASSCODE and SESSION_SECRET
(cd frontend && pnpm install && pnpm build)
cd backend && uv sync && uv run python -m wall --config ../config.yaml serve
```

Then open http://127.0.0.1:8000.

Tests run inside the image, as in CI: `docker build --target web-test .` (frontend) and
`docker build --target test .` (backend). Locally without Docker: `cd backend && uv run pytest`, `cd frontend && pnpm test`.

## Caveats

- **Google Photos:** the album is read through its public share link by parsing the album page
  (`backend/wall/sources/sharelink.py`). That format is undocumented and may change at any time; check that this
  use fits Google's terms for your situation.
- **Privacy:** downloaded photos stay in `data/` (gitignored). Run `python -m wall wipe` after the event.

## Third-party material

- `backend/models/face_landmarker.task`: Google MediaPipe Face Landmarker model, Apache License 2.0.
- `backend/golden/input/`: photos from NASA, used as a test set for the effects. NASA imagery is generally not
  subject to copyright in the US; see NASA's media usage guidelines. Its use here implies no NASA endorsement.

## License

MIT, see [LICENSE](LICENSE). The third-party material above keeps its own terms.
