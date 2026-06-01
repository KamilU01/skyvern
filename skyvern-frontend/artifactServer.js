import express from "express";
import fs from "fs";
import cors from "cors";
import { fileURLToPath } from "url";

function sendMissingRecording(res, path) {
  if (!path || typeof path !== "string") {
    return res.status(400).send("Missing path");
  }
  return res.status(404).send("Recording not found");
}

function createArtifactServer() {
  const app = express();

  app.use(cors());

  app.use((req, res, next) => {
    const start = Date.now();
    res.on("finish", () => {
      const duration = Date.now() - start;
      const timestamp = new Date().toISOString();
      const artifactPath = req.query.path || "";
      console.log(
        "[%s] %s %s %d %dms %s",
        timestamp,
        req.method,
        req.path,
        res.statusCode,
        duration,
        artifactPath,
      );
    });
    next();
  });

  app.get("/artifact/recording", (req, res, next) => {
    try {
      const range = req.headers.range;
      const path = req.query.path;
      if (!path || typeof path !== "string" || !fs.existsSync(path)) {
        return sendMissingRecording(res, path);
      }

      const videoSize = fs.statSync(path).size;
      const headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/webm",
      };

      if (videoSize === 0) {
        return res.status(204).set(headers).end();
      }

      if (!range) {
        return res
          .status(200)
          .set({
            ...headers,
            "Content-Length": videoSize,
          })
          .sendFile(path);
      }

      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      if (!match) {
        return res.status(416).set("Content-Range", `bytes */${videoSize}`).end();
      }

      const start = Number(match[1]);
      const requestedEnd = match[2] ? Number(match[2]) : start + 1 * 1e6;
      if (start >= videoSize) {
        return res.status(416).set("Content-Range", `bytes */${videoSize}`).end();
      }

      const end = Math.min(requestedEnd, videoSize - 1);
      const contentLength = end - start + 1;
      res.writeHead(206, {
        ...headers,
        "Content-Range": `bytes ${start}-${end}/${videoSize}`,
        "Content-Length": contentLength,
      });
      fs.createReadStream(path, { start, end }).pipe(res);
    } catch (err) {
      next(err);
    }
  });

  app.get("/artifact/image", (req, res) => {
    const path = req.query.path;
    res.sendFile(path);
  });

  app.get("/artifact/json", (req, res) => {
    const path = req.query.path;
    const contents = fs.readFileSync(path);
    try {
      const data = JSON.parse(contents);
      res.json(data);
    } catch (err) {
      res.status(500).send(err);
    }
  });

  app.get("/artifact/text", (req, res) => {
    const path = req.query.path;
    const contents = fs.readFileSync(path);
    res.send(contents);
  });

  app.use((err, req, res, _next) => {
    const timestamp = new Date().toISOString();
    console.error(
      "[%s] ERROR %s %s:",
      timestamp,
      req.method,
      req.path,
      err.message,
    );
    if (!res.headersSent) {
      res.status(500).send("Internal server error");
    }
  });

  return app;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createArtifactServer().listen(9090, () => {
    console.log(
      `[${new Date().toISOString()}] Artifact server running at http://localhost:9090`,
    );
  });
}

export { createArtifactServer };
