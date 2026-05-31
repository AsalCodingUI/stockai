"""Agent System Prompts.

Loads system prompts for all specialized agents from YAML files.
Falls back to inline defaults if a YAML file is missing.
"""

from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent / "prompts"

IDX_MARKET_CONTEXT = """
## Konteks Pasar IDX (Indonesia Stock Exchange)

**Karakteristik Pasar:**
- Jam trading: 09:00-16:00 WIB (Senin-Jumat), dua sesi: 09:00-12:00 dan 13:30-15:50
- Mata uang: IDR (Rupiah). Harga saham dalam Rupiah, lot = 100 lembar
- Indeks utama: IHSG (JKSE), LQ45, IDX30, JII70, IDX80
- Foreign flow (asing) sangat berpengaruh — beli asing = bullish, jual asing = bearish signal

**Sektor Utama IDX:**
- Perbankan (BBCA, BBRI, BMRI, BBNI): paling likuid, sangat korelasi dengan IHSG
- Telekomunikasi (TLKM, EXCL, ISAT): defensif, dividen tinggi
- Consumer/FMCG (UNVR, ICBP, MYOR): defensif, kuat saat ekonomi lemah
- Mining/Batubara (ADRO, ITMG, PTBA): siklikal, ikuti harga komoditas global
- Properti (BSDE, CTRA, SMRA): sensitif suku bunga BI
- Infrastruktur/Utilities (JSMR, PGAS): stabil, dividen

**Karakteristik Khusus:**
- "Saham gorengan": volume tidak wajar, free float kecil (<20%), harga bisa manipulatif — HINDARI
- Auto rejection: naik/turun >25% (untuk saham biasa) di-reject auto oleh bursa
- Emiten BUMN sering dipengaruhi kebijakan pemerintah
- Rights issue sering menyebabkan dilusi — cek apakah ada corporate action

**Faktor Makro IDX:**
- Suku bunga Bank Indonesia (BI Rate) — naik = bearish properti/consumer
- Nilai tukar USD/IDR — rupiah melemah = negatif untuk importir, positif eksportir
- Harga komoditas (CPO, batubara, nikel) — pengaruh langsung ke sektor mining
- Sentimen regional: Bursa Asia (Nikkei, Hang Seng, STI) sering mempengaruhi IHSG
"""


def _load_prompt(name: str) -> str:
    """Load a system_prompt string from a YAML file in the prompts/ directory."""
    yaml_path = _PROMPTS_DIR / f"{name}.yaml"
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"].rstrip()


MARKET_SCANNER_PROMPT = _load_prompt("market_scanner")
RESEARCH_AGENT_PROMPT = _load_prompt("research_agent")
TECHNICAL_ANALYST_PROMPT = _load_prompt("technical_analyst")
SENTIMENT_ANALYST_PROMPT = _load_prompt("sentiment_analyst")
PORTFOLIO_MANAGER_PROMPT = _load_prompt("portfolio_manager")
RISK_MANAGER_PROMPT = _load_prompt("risk_manager")
TRADING_EXECUTION_PROMPT = _load_prompt("trading_execution")
ORCHESTRATOR_PROMPT = IDX_MARKET_CONTEXT + "\n\n" + _load_prompt("orchestrator")
