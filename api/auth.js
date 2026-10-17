const ALLOWED = new Set([
  "auth/register",
  "auth/login",
  "auth/forgot-password",
  "auth/reset-password",
  "auth/me",
  "auth/logout",
]);

module.exports = async function handler(req, res) {
  const path = String(req.query.path || "");
  if (!ALLOWED.has(path)) {
    res.status(404).json({ message: "Unknown account path." });
    return;
  }

  const headers = { Accept: "application/json" };
  if (req.headers.authorization) headers.Authorization = req.headers.authorization;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  if (hasBody) headers["Content-Type"] = "application/json";

  let upstream;
  try {
    upstream = await fetch("https://stem.iconiaglobal.com/api/v1/" + path, {
      method: req.method,
      headers,
      body: hasBody ? JSON.stringify(req.body || {}) : undefined,
    });
  } catch (error) {
    res.status(502).json({ message: "The account service did not answer. Try again." });
    return;
  }

  const text = await upstream.text();
  res.status(upstream.status);
  res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
  res.send(text);
};
