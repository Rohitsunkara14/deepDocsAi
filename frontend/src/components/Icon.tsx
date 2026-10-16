import { FileText } from "lucide-react";
export function Brand({ small = false }: { small?: boolean }) {
  return (
    <div className={`brand ${small ? "small" : ""}`}>
      <span className="brand-mark">
        <FileText size={23} strokeWidth={1.6} />
      </span>
      <span>
        DeepDocs <b>AI</b>
      </span>
    </div>
  );
}
