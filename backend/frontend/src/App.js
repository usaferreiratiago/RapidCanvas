import React, { useState, useRef } from "react";
import "./App.css";

const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

const EXAMPLE_POSTS = [
  {
    label: "Ralph Wiggum technique",
    text: "Ralph Wiggum is the craziest thing to happen in coding agents in 2026 so far",
  },
  {
    label: "MCP protocol",
    text: "MCP is quietly becoming the USB-C of AI tooling. Every framework just... adopted it.",
  },
  {
    label: "GPT-5 hype",
    text: "GPT-5 drops and suddenly everyone's a prompt engineer again 💀",
  },
];

function Bullet({ text, source, source_url, index }) {
  return (
    <div className="bullet" style={{ animationDelay: `${index * 0.1}s` }}>
      <span className="bullet-marker">▸</span>
      <div className="bullet-content">
        <p className="bullet-text">{text}</p>
        {source && (
          <a
            className="bullet-source"
            href={source_url || "#"}
            target="_blank"
            rel="noopener noreferrer"
          >
            ↗ {source}
          </a>
        )}
      </div>
    </div>
  );
}

function ComparePanel({ data }) {
  return (
    <div className="compare-panel">
      <h3 className="compare-title">Provider Comparison</h3>
      <div className="compare-grid">
        {data.results.map((r) => (
          <div key={r.model} className="compare-card">
            <div className="compare-header">
              <span className="compare-model">{r.model}</span>
              <span className="compare-latency">{Math.round(r.latency_ms)}ms</span>
            </div>
            {r.error ? (
              <p className="compare-error">{r.error}</p>
            ) : (
              <ul className="compare-bullets">
                {r.bullets.map((b, i) => (
                  <li key={i}>{b.text}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("url"); // "url" | "text"
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [compareData, setCompareData] = useState(null);
  const [error, setError] = useState(null);
  const [showCompare, setShowCompare] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const fileRef = useRef();

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const explain = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCompareData(null);

    try {
      const body = mode === "url" ? { url: input } : { text: input };
      if (imagePreview) body.image_url = imagePreview;

      const res = await fetch(`${API}/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const compare = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const body = mode === "url" ? { url: input } : { text: input };
      const res = await fetch(`${API}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setCompareData(data);
      setShowCompare(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      {/* Background noise */}
      <div className="bg-noise" />

      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">◈</span>
            <span className="logo-text">CONTEXT</span>
          </div>
          <p className="tagline">AI-powered post explainer</p>
        </div>
      </header>

      <main className="main">
        {/* Input section */}
        <section className="input-section">
          <div className="mode-tabs">
            <button
              className={`mode-tab ${mode === "url" ? "active" : ""}`}
              onClick={() => setMode("url")}
            >
              URL
            </button>
            <button
              className={`mode-tab ${mode === "text" ? "active" : ""}`}
              onClick={() => setMode("text")}
            >
              RAW TEXT
            </button>
          </div>

          <div className="input-wrapper">
            {mode === "url" ? (
              <input
                className="input-field"
                type="text"
                placeholder="https://bsky.app/profile/user/post/..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && explain()}
              />
            ) : (
              <textarea
                className="input-field textarea"
                placeholder="Paste any social media post text here…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={4}
              />
            )}
          </div>

          {/* Image upload */}
          <div className="image-section">
            <button
              className="image-btn"
              onClick={() => fileRef.current.click()}
            >
              {imagePreview ? "✓ Image attached" : "+ Attach image"}
            </button>
            {imagePreview && (
              <button
                className="image-clear"
                onClick={() => { setImageFile(null); setImagePreview(null); }}
              >
                ✕
              </button>
            )}
            <input
              type="file"
              accept="image/*"
              ref={fileRef}
              style={{ display: "none" }}
              onChange={handleImageUpload}
            />
            {imagePreview && (
              <img className="image-thumb" src={imagePreview} alt="preview" />
            )}
          </div>

          {/* Examples */}
          <div className="examples">
            <span className="examples-label">Try:</span>
            {EXAMPLE_POSTS.map((ex) => (
              <button
                key={ex.label}
                className="example-chip"
                onClick={() => { setMode("text"); setInput(ex.text); }}
              >
                {ex.label}
              </button>
            ))}
          </div>

          <div className="actions">
            <button
              className="btn btn-primary"
              onClick={explain}
              disabled={loading || !input.trim()}
            >
              {loading ? (
                <span className="btn-loading">
                  <span className="spinner" /> Researching…
                </span>
              ) : (
                "EXPLAIN"
              )}
            </button>
            <button
              className="btn btn-secondary"
              onClick={compare}
              disabled={loading || !input.trim()}
              title="Compare GPT-4o vs GPT-4o-mini"
            >
              COMPARE MODELS
            </button>
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="error-box">
            <span className="error-icon">!</span> {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <section className="results-section">
            {/* Post meta */}
            {(result.post_author || result.platform) && (
              <div className="post-meta">
                {result.platform && (
                  <span className="meta-platform">{result.platform.toUpperCase()}</span>
                )}
                {result.post_author && (
                  <span className="meta-author">@{result.post_author}</span>
                )}
              </div>
            )}

            {/* Post text */}
            {result.post_text && (
              <div className="post-preview">
                <p>{result.post_text}</p>
              </div>
            )}

            {/* Image description */}
            {result.image_description && (
              <div className="image-desc">
                <span className="image-desc-label">IMAGE</span>
                <p>{result.image_description}</p>
              </div>
            )}

            {/* Bullets */}
            <div className="bullets-header">
              <span className="bullets-label">CONTEXT</span>
              <span className="bullets-count">{result.bullets.length} insights</span>
            </div>
            <div className="bullets-list">
              {result.bullets.map((b, i) => (
                <Bullet key={i} {...b} index={i} />
              ))}
            </div>

            {/* Search queries used */}
            {result.search_queries_used?.length > 0 && (
              <div className="queries-used">
                <span className="queries-label">SEARCHED</span>
                <div className="query-tags">
                  {result.search_queries_used.map((q, i) => (
                    <span key={i} className="query-tag">{q}</span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Compare panel */}
        {showCompare && compareData && (
          <ComparePanel data={compareData} />
        )}
      </main>

      <footer className="footer">
        <span>RapidCanvas · Post Explainer · 2025</span>
      </footer>
    </div>
  );
}
