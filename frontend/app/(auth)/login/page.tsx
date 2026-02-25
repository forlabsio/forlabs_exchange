"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const [error, setError] = useState("");
  const { connectWallet, connecting } = useAuthStore();
  const router = useRouter();

  const handleConnect = async () => {
    setError("");
    try {
      await connectWallet();
      router.push("/exchange/BTC_USDT");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "연결에 실패했습니다.";
      setError(message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-primary)" }}>
      <div className="w-full max-w-sm p-8 rounded-lg" style={{ background: "var(--bg-panel)", border: "1px solid var(--border)" }}>
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>ForLabsEX</h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
          MetaMask 지갑을 연결하여 시작하세요
        </p>
        {error && <p className="text-sm mb-4" style={{ color: "var(--red)" }}>{error}</p>}
        <button
          type="button"
          onClick={handleConnect}
          disabled={connecting}
          className="w-full py-3 rounded font-semibold text-white flex items-center justify-center gap-2"
          style={{ background: connecting ? "#666" : "#f6851b" }}
        >
          {connecting ? "연결 중..." : "MetaMask 연결"}
        </button>
        <p className="mt-4 text-xs text-center" style={{ color: "var(--text-secondary)" }}>
          MetaMask가 없으신가요?{" "}
          <a href="https://metamask.io/download/" target="_blank" rel="noopener noreferrer" style={{ color: "var(--blue)" }}>
            설치하기
          </a>
        </p>
      </div>
    </div>
  );
}
