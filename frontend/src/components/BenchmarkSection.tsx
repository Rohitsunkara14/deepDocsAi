import { ArrowRight, FlaskConical } from "lucide-react";
const rows = [
  ["Dense", "0.3369", "0.3901", "19.23"],
  ["BM25", "0.6010", "0.5969", "74.51"],
  ["Hybrid", "0.5891", "0.6277", "93.58"],
  ["Hybrid + rerank", "0.7174", "0.6936", "483.71"],
];
export function BenchmarkSection() {
  return (
    <section className="benchmark-section" id="benchmark">
      <div className="benchmark-top">
        <div>
          <span className="eyebrow">
            <FlaskConical size={14} /> BUILT TO BE MEASURED
          </span>
          <h2>Evidence behind the architecture.</h2>
        </div>
        <p>
          30-question assistant-reviewed development benchmark over 11,769
          chunks from seven annual reports.
        </p>
      </div>
      <div className="benchmark-grid">
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Measured retrieval comparison on the development corpus
            </caption>
            <thead>
              <tr>
                <th>Retrieval strategy</th>
                <th>Recall@5</th>
                <th>MRR@10</th>
                <th>
                  P50 <span>ms</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r[0]} className={i === 3 ? "best" : ""}>
                  <th>
                    {r[0]}
                    {i === 3 && (
                      <span className="quality-tag">Best quality</span>
                    )}
                  </th>
                  {r.slice(1).map((v, j) => (
                    <td key={j}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="benchmark-insight">
          <span className="big-metric">0.7174</span>
          <h3>Recall@5 with reranking</h3>
          <p>
            Reranking leads on overall quality. Dense offers the lowest measured
            latency.
          </p>
          <p className="fine-print">
            Five runs · 26 answerable cases scored
            <br />
            Local retrieval timing; excludes generation.
            <br />
            Development results, not general model performance.
          </p>
        </div>
      </div>
      <div className="architecture-flow" aria-label="System architecture">
        {[
          "PDF / TXT",
          "Page-aware chunks",
          "Embeddings + Qdrant",
          "Hybrid RRF + rerank",
          "Grounded answer",
        ].map((v, i) => (
          <span key={v}>
            {i > 0 && <ArrowRight size={14} />}
            <span>{v}</span>
          </span>
        ))}
      </div>
      <div className="feature-line">
        Semantic + lexical retrieval <span>·</span> Cross-encoder reranking{" "}
        <span>·</span> Grounded LLM answers <span>·</span> Page-level citations{" "}
        <span>·</span> Evaluation framework
      </div>
    </section>
  );
}
