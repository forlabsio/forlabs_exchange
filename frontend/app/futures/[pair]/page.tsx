export default function FuturesPage({ params }: { params: { pair: string } }) {
  return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>선물 거래</h1>
        <p style={{ color: "var(--text-secondary)" }}>준비 중입니다.</p>
      </div>
    </div>
  );
}
