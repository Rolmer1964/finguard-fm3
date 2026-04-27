import { Bar } from "react-chartjs-2";
import { BarElement, CategoryScale, Chart, Legend, LinearScale, Title, Tooltip } from "chart.js";

Chart.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function CategoryChart({ title, data, color }: { title: string; data: Record<string, number>; color: string }) {
  const labels = Object.keys(data);
  const values = Object.values(data);
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <Bar
        data={{ labels, datasets: [{ data: values, backgroundColor: color }] }}
        options={{
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        }}
      />
    </div>
  );
}
