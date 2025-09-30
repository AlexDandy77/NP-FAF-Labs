# PR Lab 1 – HTTP File Server Report

**Student:** Alexei Pavlovschii, FAF-231
**Course:** Network Programming (PR)  
**Instructor:** Artiom Balan  
**Deadline:** Oct 14, 2025  
**Repository:** [GitHub Link](https://github.com/AlexDandy77/NP-FAF-Labs/)

---

## 1. Goal

Implement a minimal HTTP server using **raw TCP sockets** that:
- Handles one HTTP request at a time.
- Serves files from a chosen directory (`.html`, `.png`, `.pdf`).
- Returns a **404 custom page** for missing or unsupported files.
- Provides directory listings for nested folders.
- Runs inside **Docker** using **Docker Compose**.
- Includes a simple **Python client** for testing.

---

## 2. Project Structure

```
pr-/
├── server.py           # HTTP server
├── client.py           # HTTP client
├── Dockerfile          # Container definition
├── docker-compose.yml  # Run configuration
├── REPORT.md           # This report
└── www/                # Content directory
    ├── index.html
    ├── 404.html
    ├── subdir/info.html
    ├── images/sample.png
    └── books/
        ├── crypto/crypto.pdf
        ├── book1.pdf
        └── book2.pdf
```
---

## 3. Running Locally (No Docker)

### Command
```bash
python server.py ./www
```

### Screenshot – server start

![image](screenshots/server-start.png)
Shows the HTTP server starting up and listening on port 8080

### Screenshot – directory listing

![image](screenshots/listing.png)
Displays the contents of the root directory with files and folders

### Screenshot – browser request (index.html)

![image](screenshots/index.png)
Shows the main index.html page being served in the browser

### Screenshot – subdirectory listing (books)

![image](screenshots/books.png)
Lists the contents of the books subdirectory containing PDF files

### Screenshot – opening a file

![image](screenshots/open-file.png)
Demonstrates opening and viewing a file from the server

### Screenshot – 404 page

![image](screenshots/404.png)

Shows the custom 404 error page when requesting a non-existent file

---

## 4. Running with Docker

### Build and run with Docker Compose
```bash
docker compose up --build
```

### Screenshot – container start

![image](screenshots/docker-run.png)
Shows Docker container starting up successfully with the HTTP server listening on port 8080

### Screenshot – browser access at http://localhost:8080

![image](screenshots/docker-browser.png)
Demonstrates accessing the HTTP server through a web browser after Docker container deployment

---

## 5. Client Tests

### Download a file with client.py:
```bash
python client.py http://127.0.0.1:8080/books/book1.pdf ./downloads
```

### Screenshot – file saved
![image](screenshots/client-save-file.png)

### Open a .html file with client.py: 
```bash
python client.py http://127.0.0.1:8080/index.html ./downloads
```
### Screenshot – displayed html content
![image](screenshots/open-html.png)

---

## 6. Key Components

| Component | Purpose |
|------------|----------|
| `server.py` | Handles incoming TCP connections, parses GET requests, sends files or directory listings. |
| `client.py` | Connects to server, downloads files or prints HTML body. |
| `Dockerfile` | Defines how to build a Python-based container. |
| `docker-compose.yml` | Describes how to run and expose the container. |
| `404.html` | Custom page for missing resources. |
| `SO_REUSEADDR` | Allows server restart on same port immediately. |
---
> The project demonstrates practical understanding of TCP sockets, HTTP fundamentals, and Docker workflow.
