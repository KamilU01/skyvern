import fs from "fs";
import http from "http";
import os from "os";
import path from "path";
import { afterEach, describe, expect, it } from "vitest";

import { createArtifactServer } from "./artifactServer.js";

const servers = [];

async function startServer(app) {
  const server = http.createServer(app);
  servers.push(server);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

function writeTempRecording(contents = "recording-bytes") {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "skyvern-recording-"));
  const filePath = path.join(dir, "recording.webm");
  fs.writeFileSync(filePath, contents);
  return filePath;
}

afterEach(async () => {
  await Promise.all(
    servers.splice(0).map(
      (server) =>
        new Promise((resolve, reject) => {
          server.close((error) => (error ? reject(error) : resolve()));
        }),
    ),
  );
});

describe("artifact recording server", () => {
  it("serves a full recording when the client omits a range header", async () => {
    const filePath = writeTempRecording("complete-recording");
    const baseUrl = await startServer(createArtifactServer());

    const response = await fetch(
      `${baseUrl}/artifact/recording?path=${encodeURIComponent(filePath)}`,
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("video/webm");
    expect(await response.text()).toBe("complete-recording");
  });

  it("serves byte ranges for browser video playback", async () => {
    const filePath = writeTempRecording("0123456789");
    const baseUrl = await startServer(createArtifactServer());

    const response = await fetch(
      `${baseUrl}/artifact/recording?path=${encodeURIComponent(filePath)}`,
      { headers: { Range: "bytes=2-5" } },
    );

    expect(response.status).toBe(206);
    expect(response.headers.get("content-range")).toBe("bytes 2-5/10");
    expect(await response.text()).toBe("2345");
  });
});
