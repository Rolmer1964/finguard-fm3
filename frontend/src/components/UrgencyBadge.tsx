export default function UrgencyBadge({ value }: { value?: string | null }) {
  if (!value) return <span className="pill neutral">-</span>;
  const v = value.toLowerCase();
  let cls = "neutral";
  if (v.startsWith("crít")) cls = "crit";
  else if (v.startsWith("alt")) cls = "alta";
  else if (v.startsWith("méd") || v.startsWith("med")) cls = "media";
  else if (v.startsWith("baix")) cls = "baixa";
  return <span className={`pill ${cls}`}>{value}</span>;
}
