# Testing with real documents

How to evaluate this platform against genuine policy and evidence documents without those documents
leaving your machine, entering this git repository, or syncing to a cloud drive.

For a first look at the platform using the built-in synthetic samples, you do not need this document —
see `data/sample_evidence/README.md` and `deployment/README.md`. This one is specifically about the
handling rules that apply once the documents are real.

---

## Read this first

**Use the Docker deployment. Do not use the local development mode.**

That single choice is what keeps real documents out of this repository and out of any synced folder.
Everything else in this document is detail.

This repository is **public**, and a developer's working copy frequently lives inside a
cloud-synced folder (OneDrive, Dropbox, Google Drive). Those two facts are why the distinction below
matters more here than it would in a normal project.

---

## Why the Docker path is safe

Not a promise — a property of how the stack is wired.

**1. The application cannot transmit document content anywhere.**

- No cloud AI. Retrieval-only is this platform's permanent architecture, formally decided rather than
  deferred (ADR-0020, reconfirmed ADR-0036).
- Embeddings run locally against an ONNX model on disk (ADR-0008).
- OCR runs locally; its models ship *inside* the installed Python package, so nothing is fetched at
  runtime (ADR-0055).

There is no code path from evidence content to a network call.

**2. Real documents never touch the repository.**

The only things `deployment/docker-compose.yml` mounts from the repo are three read-only secrets:

```
- ./secrets/.htpasswd :ro
- ./secrets/tls.crt   :ro
- ./secrets/tls.key   :ro
```

Everything the application writes — uploaded originals, extracted text, the vector store, the
database — goes to a Docker named volume:

```
/var/lib/docker/volumes/deployment_compliance-data/_data
```

That is Docker's own storage. Not the repo, not git, not your synced drive. Consequently
`.cursor/rules/privacy-protection.mdc`'s rule that only public or synthetic material may exist under
`data/` is not strained by this workflow — under Docker, `data/` never sees a real document at all.

---

## The one thing that breaks it

**Local development mode** (`uvicorn` + `npm run dev`) writes:

| What | Where |
|---|---|
| Retained original uploads | `<repo>/data/raw/` |
| Extracted text, vector store, database | `<repo>/data/processed/` |

Both are inside the working copy. If that working copy sits in a synced folder, **real documents sync
to your organisation's cloud**. Both paths are gitignored, so an accidental `git add -A` will not
commit them — but gitignore does not stop OneDrive.

Use local development mode for synthetic samples and for writing code. Not for real documents.

---

## Setup

Prerequisites: **Docker Desktop** (running) and **Git**. On Windows use Git Bash, and enable
Docker Desktop → Settings → Resources → WSL Integration.

### 1. Get the code

```bash
git clone https://github.com/fraz7900/ai-augmented-assessment-framework.git
cd ai-augmented-assessment-framework/deployment
```

If your machine keeps its projects inside a synced folder, clone somewhere else — outside
OneDrive/Dropbox. Under Docker no document data lands there, but keeping the whole working copy out
of a synced tree removes the question entirely.

### 2. Create credentials — use a real password

nginx refuses to start without these. That is deliberate fail-closed behaviour (ADR-0045, ADR-0047),
not a bug.

```bash
mkdir -p secrets

# Choose a genuine password here. Do NOT reuse the throwaway from the demo guide.
docker run --rm httpd:alpine htpasswd -Bbn <your-username> '<a-strong-password>' > secrets/.htpasswd

docker run --rm -v "$PWD/secrets:/secrets" alpine/openssl req -x509 -nodes \
  -newkey rsa:2048 -days 825 -keyout /secrets/tls.key -out /secrets/tls.crt \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

`secrets/` is gitignored. Never commit it.

### 3. Start, and keep it on localhost

```bash
docker compose up -d --build     # first build ~5-10 min
docker compose ps                # wait for backend = healthy
```

Open **https://localhost:5173** and accept the self-signed certificate warning.

**Do not publish port 5173 to a network.** The certificate is self-signed and HTTP basic auth is the
only access control. This stack is designed for single-user or small-team use on a trusted machine
(see `deployment/README.md`), not for shared hosting.

---

## What to test, and what you learn from it

Real documents are worth the handling overhead because they expose things synthetic samples cannot.

| Upload | What it actually tests |
|---|---|
| A **scanned** PDF (photocopy, signed page) | OCR accuracy on real scan quality, skew, and fonts — the generated sample is clean by construction |
| A long **policy PDF** with headers/footers | Whether running-header stripping works on real page furniture, and whether page-number citations land on the right page |
| A document with **tables** | Table flattening, which is a known weak point (`.cursor/rules/document-parsing.mdc`) |
| A **spreadsheet** register | Row and sheet citations against real column layouts |
| Several documents for **one control** | Whether retrieval actually surfaces the right passage among competing candidates |

Then work the review flow end to end: link evidence to a control, run **Propose AI mappings**, and
accept/edit/reject. The question worth answering is not "did it produce output" but **"would I sign
my name to this finding?"** That is what synthetic data cannot tell you.

### Expect OCR to be imperfect

OCR text is approximate, which is why it is surfaced as a distinct status with an explicit warning
rather than presented as a clean read. Observed on the synthetic sample: words occasionally run
together (`quarterlybasis`), and wide letter-spaced headings can lose their spaces. On real scans,
expect worse. Judge it as "is this good enough to cite, after a human reads it" — the design
assumption is that a human does.

---

## Handling what comes out

- **Downloaded reports** (PDF/XLSX) go to your browser's Downloads folder. Those are on your normal
  disk, outside Docker — treat them like any other client document.
- **Screenshots and screen-sharing** will show real content. Take care when demoing, and never paste
  a screenshot containing real content into an issue, commit, or this public repo.
- **Sanitization** is built in (preview → human approval → sanitized export, ADR-0032) if you need to
  share output with content removed.

---

## Cleanup

```bash
cd deployment
docker compose down -v
```

**The `-v` matters.** Without it the volume survives and the documents stay on disk indefinitely.

Then confirm nothing reached the working copy:

```bash
git status                       # expect no new files under data/
ls data/raw data/processed       # expect only README.md / synthetic material
```

---

## Checklist

Before:

- [ ] Docker deployment, not local development mode
- [ ] Strong password in `secrets/.htpasswd`
- [ ] Port 5173 not exposed beyond localhost
- [ ] Working copy outside any synced folder (belt and braces)

After:

- [ ] `docker compose down -v`
- [ ] `git status` shows nothing new under `data/`
- [ ] Downloaded reports moved or deleted

---

## What this document does not decide

It establishes that the software keeps documents on your machine. It does not establish that you are
permitted to put a given document into it. Organisational policy, client NDAs, and programme rules
are separate questions with separate answers, and they belong to whoever owns the documents.

If you want realistic input without that question at all, use genuinely public material — a published
regulation, a utility's posted security policy, a public university's IT standards. Real formatting,
real language, real scan quality, no confidentiality.
