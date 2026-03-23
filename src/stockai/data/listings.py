"""IDX Stock Listings Database.

Provides comprehensive list of Indonesian stocks with search capabilities.
Updated with IDX30, LQ45, and other major stocks as of 2025.
"""

import asyncio
import gzip
import json
import logging
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

IDX_STOCK_LIST_URL = (
    "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
    "?start=0&length=9999&language=id"
)
IDX_STOCK_LIST_URL_ALT = (
    "https://www.idx.co.id/api/stock-universe"
    "?start=0&length=9999"
)
YAHOO_SCREENER_URLS = [
    "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
    "?scrIds=most_actives&start={start}&count=250",
    "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    "?scrIds=most_actives&start={start}&count=250",
]
IDX_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.idx.co.id/id/data-pasar/data-saham/daftar-saham/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}
UNIVERSE_CACHE_FILE = Path.home() / ".stockai" / "idx_universe.json"
CACHE_TTL_DAYS = 7

# Seed list 500+ ticker kandidat IDX untuk yfinance bulk validate.
KNOWN_IDX_PREFIXES = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BNLI", "PNBN", "BJTM", "BJBR",
    "BNGA", "BDMN", "NISP", "MAYA", "BSIM", "MCOR", "AGRO", "ARTO", "BANK", "BBYB",
    "DNAR", "HANA", "IBOS", "INAS", "INPC", "NAGA", "PNBS", "SDRA", "SEAH", "NOBU",
    "BVIC", "BCIC", "BMAS", "BGTG", "BINA", "BMSI", "BNBA", "BNII", "BPFI", "BSWD",
    "ADRO", "PTBA", "ITMG", "HRUM", "BUMI", "DEWA", "KKGI", "MYOH", "ADMR", "DOID",
    "INDY", "BREN", "ESSA", "AKRA", "PGAS", "MEDC", "ENRG", "BIPI", "ELSA", "RUIS",
    "PTRO", "ARTI", "GTBO", "SMMT", "PSAB", "FIRE", "MBAP", "GEMS", "TOBA", "MCOL",
    "PKPK", "KPIG", "BORN", "BRAU", "BSSR", "GTBO", "HITS", "ARII", "CNKO", "SMRU",
    "ANTM", "INCO", "TINS", "MDKA", "AMMN", "NCKL", "BRMS", "PSAB", "SMBR", "ZINC",
    "CTTH", "DKFT", "KING", "MITI", "SMCB", "PURE", "IFSH", "IPPE", "MITI", "PBTH",
    "UNVR", "ICBP", "INDF", "MYOR", "ULTJ", "ROTI", "CLEO", "DLTA", "MLBI", "BUDI",
    "ALTO", "CAMP", "CEKA", "GOOD", "HOKI", "KEJU", "STTP", "SKBM", "SKLT", "SMAR",
    "AISA", "TBLA", "PANI", "HMSP", "GGRM", "WIIM", "RMBA", "ITIC", "DMND", "FOOD",
    "PSGO", "KINO", "LMPI", "SIGER", "ADES", "DAVO", "DKFT", "ERNZ", "FAST", "HKMU",
    "TLKM", "EXCL", "ISAT", "LINK", "FREN", "MORA", "SUPR", "TOWR", "TBIG", "BALI",
    "DMMX", "EMTK", "MNCN", "SCMA", "MEJA", "MTDL", "MLPT", "GOTO", "BUKA", "GLVA",
    "EDGE", "EKAD", "EPMT", "KIOS", "LUCK", "MCAS", "MTFN", "PGEO", "RELI", "RUNS",
    "BSDE", "CTRA", "PWON", "SMRA", "LPKR", "DART", "DMAS", "JRPT", "MDLN", "MTLA",
    "PLIN", "PPRO", "RBMS", "RODA", "TARA", "ASRI", "BKSL", "CITY", "DUTI", "GPRA",
    "KIJA", "LAND", "LPCK", "APLN", "PANI", "POLL", "BIKA", "BIPP", "COWL", "DILD",
    "ELTY", "FMII", "GMTD", "GWSA", "MKPI", "MMLP", "MTSM", "NIRO", "POLI", "PUDP",
    "RDTX", "REAL", "RISE", "ROCK", "SCBD", "SMDM", "TRIN",
    "KLBF", "SIDO", "MERK", "KAEF", "PEHA", "DVLA", "TSPC", "PYFA", "INAF", "SCPI",
    "MIKA", "HEAL", "PRAY", "SILO", "SAME", "SHID", "PRIM", "CARE", "IRRA", "OMED",
    "JSMR", "WSKT", "PTPP", "WIKA", "ADHI", "NRCA", "TOTL", "ACST", "DGIK", "IDPR",
    "PBSA", "WTON", "BTON", "SMBR", "SMGR", "INTP", "PORT", "META", "CMNP", "IPCM",
    "LRNA", "NELY", "SAFE", "SDMU", "GIAA", "ASSA", "BIRD", "BLTA", "CMPP", "HATM",
    "MBSS", "SMDR", "TMAS", "WINS", "TPMA", "BPTR", "CASS", "INDX", "ISSP", "KJEN",
    "ASII", "AUTO", "IMAS", "INDS", "LPIN", "PRAS", "SMSM", "BOLT", "GDYR", "GJTL",
    "MASA", "NIPS", "PCAR", "RICY", "SSTM", "VOKS", "PBRX", "CNTX", "BELL", "BATA",
    "BIMA", "CFIN", "DYAN", "ESTI", "MYTX", "PAFI", "SRIL", "POLY", "HDTX", "UNIT",
    "MAPI", "RALS", "LPPF", "MIDI", "MPPA", "ACES", "CSAP", "DAYA", "ECII", "ERAA",
    "GLOB", "HOME", "HERO", "KOIN", "KPAS", "MEDS", "SONA", "SKYB", "RANC", "TELE",
    "AALI", "LSIP", "SSMS", "BWPT", "DSFI", "GZCO", "JAWA", "MAGP", "PALM", "SGRO",
    "SIMP", "ANJT", "TAPG", "TBLA", "MGRO", "BTEK", "DNSG", "FAPA", "IIKP", "KDSI",
    "LSIP", "NSSS", "SMAR", "SPOT", "UNSP", "WAPO",
    "ADMF", "BFIN", "CFIN", "MFIN", "TIFA", "VRNA", "WOMF", "HDFA", "IMJS", "INCF",
    "PADI", "PEGE", "SMMA", "ABDA", "AHAP", "AMAG", "ASBI", "ASDM", "ASEI", "ASMI",
    "ASRM", "LPGI", "MREI", "PNIN", "TUGU", "SRTG", "BCAP", "DEFI", "FUJI", "GSMF",
    "JMAS", "MAMI", "OCAP", "PANS", "PEGE", "POOL", "VINS", "YULE",
    "FILM", "JTPE", "KREN", "MSIN", "MSKY", "TMPO", "VIVA", "BMTR", "FORU", "MNCN",
    "ASSA", "BIRD", "GIAA", "TMAS", "WINS", "CMPP", "BLTA", "MBSS", "SMDR", "SDMU",
    "NELY", "HATM", "LRNA", "PORT", "SAFE", "IPCM", "CASS", "BPTR", "TPMA", "INDX",
    "AGII", "AKPI", "ALKA", "ALMI", "AMFG", "ARNA", "BTON", "CTBN", "DPNS", "EKAD",
    "FASW", "IGAR", "IGBR", "IMPC", "IPOL", "ISSP", "JECC", "JPRS", "KDSI", "KIAS",
    "KRAH", "LION", "LMSH", "MAIN", "MARK", "MDKI", "MLIA", "MOLI", "MREI", "MYOR",
    "NIKL", "PICO", "PRAS", "SRSN", "TBMS", "TOTO", "TRST", "UNIC", "VOKS", "YPAS",
]


# IDX30 stocks (most liquid 30 stocks)
IDX30_STOCKS = [
    {"symbol": "ACES", "name": "Ace Hardware Indonesia", "sector": "Consumer Cyclicals"},
    {"symbol": "ADRO", "name": "Adaro Energy Indonesia", "sector": "Energy"},
    {"symbol": "AMRT", "name": "Sumber Alfaria Trijaya", "sector": "Consumer Cyclicals"},
    {"symbol": "ANTM", "name": "Aneka Tambang", "sector": "Basic Materials"},
    {"symbol": "ASII", "name": "Astra International", "sector": "Consumer Cyclicals"},
    {"symbol": "BBCA", "name": "Bank Central Asia", "sector": "Finance"},
    {"symbol": "BBNI", "name": "Bank Negara Indonesia", "sector": "Finance"},
    {"symbol": "BBRI", "name": "Bank Rakyat Indonesia", "sector": "Finance"},
    {"symbol": "BBTN", "name": "Bank Tabungan Negara", "sector": "Finance"},
    {"symbol": "BMRI", "name": "Bank Mandiri", "sector": "Finance"},
    {"symbol": "BRPT", "name": "Barito Pacific", "sector": "Basic Materials"},
    {"symbol": "BUKA", "name": "Bukalapak.com", "sector": "Technology"},
    {"symbol": "CPIN", "name": "Charoen Pokphand Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "EMTK", "name": "Elang Mahkota Teknologi", "sector": "Technology"},
    {"symbol": "ESSA", "name": "Surya Esa Perkasa", "sector": "Energy"},
    {"symbol": "GOTO", "name": "GoTo Gojek Tokopedia", "sector": "Technology"},
    {"symbol": "HRUM", "name": "Harum Energy", "sector": "Energy"},
    {"symbol": "ICBP", "name": "Indofood CBP Sukses Makmur", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "INCO", "name": "Vale Indonesia", "sector": "Basic Materials"},
    {"symbol": "INDF", "name": "Indofood Sukses Makmur", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "INKP", "name": "Indah Kiat Pulp & Paper", "sector": "Basic Materials"},
    {"symbol": "ITMG", "name": "Indo Tambangraya Megah", "sector": "Energy"},
    {"symbol": "KLBF", "name": "Kalbe Farma", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "MDKA", "name": "Merdeka Copper Gold", "sector": "Basic Materials"},
    {"symbol": "PGAS", "name": "Perusahaan Gas Negara", "sector": "Energy"},
    {"symbol": "SMGR", "name": "Semen Indonesia", "sector": "Basic Materials"},
    {"symbol": "TBIG", "name": "Tower Bersama Infrastructure", "sector": "Infrastructures"},
    {"symbol": "TLKM", "name": "Telkom Indonesia", "sector": "Infrastructures"},
    {"symbol": "TOWR", "name": "Sarana Menara Nusantara", "sector": "Infrastructures"},
    {"symbol": "UNTR", "name": "United Tractors", "sector": "Industrials"},
]

# LQ45 stocks (45 most liquid - includes IDX30 plus 15 more)
LQ45_ADDITIONAL = [
    {"symbol": "AKRA", "name": "AKR Corporindo", "sector": "Energy"},
    {"symbol": "BRIS", "name": "Bank Syariah Indonesia", "sector": "Finance"},
    {"symbol": "BSDE", "name": "Bumi Serpong Damai", "sector": "Property & Real Estate"},
    {"symbol": "CTRA", "name": "Ciputra Development", "sector": "Property & Real Estate"},
    {"symbol": "ERAA", "name": "Erajaya Swasembada", "sector": "Consumer Cyclicals"},
    {"symbol": "EXCL", "name": "XL Axiata", "sector": "Infrastructures"},
    {"symbol": "HMSP", "name": "HM Sampoerna", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "INTP", "name": "Indocement Tunggal Prakarsa", "sector": "Basic Materials"},
    {"symbol": "ISAT", "name": "Indosat Ooredoo Hutchison", "sector": "Infrastructures"},
    {"symbol": "JPFA", "name": "Japfa Comfeed Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "JSMR", "name": "Jasa Marga", "sector": "Infrastructures"},
    {"symbol": "MAPI", "name": "Mitra Adiperkasa", "sector": "Consumer Cyclicals"},
    {"symbol": "MEDC", "name": "Medco Energi Internasional", "sector": "Energy"},
    {"symbol": "MYOR", "name": "Mayora Indah", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "PTBA", "name": "Bukit Asam", "sector": "Energy"},
]

# JII70 stocks (Jakarta Islamic Index 70 - 70 most liquid sharia-compliant stocks)
# Note: JII70 excludes conventional banks and non-halal businesses
JII70_STOCKS = [
    # Top tier by market cap
    {"symbol": "AMMN", "name": "Amman Mineral Internasional", "sector": "Basic Materials"},
    {"symbol": "TLKM", "name": "Telkom Indonesia", "sector": "Infrastructures"},
    {"symbol": "BYAN", "name": "Bayan Resources", "sector": "Energy"},
    {"symbol": "TPIA", "name": "Chandra Asri Pacific", "sector": "Basic Materials"},
    {"symbol": "ASII", "name": "Astra International", "sector": "Consumer Cyclicals"},
    {"symbol": "GOTO", "name": "GoTo Gojek Tokopedia", "sector": "Technology"},
    {"symbol": "DSSA", "name": "Dian Swastatika Sentosa", "sector": "Energy"},
    {"symbol": "UNTR", "name": "United Tractors", "sector": "Industrials"},
    {"symbol": "INDF", "name": "Indofood Sukses Makmur", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "PANI", "name": "Pantai Indah Kapuk Dua", "sector": "Property & Real Estate"},
    # High market cap sharia stocks
    {"symbol": "BRPT", "name": "Barito Pacific", "sector": "Basic Materials"},
    {"symbol": "BRMS", "name": "Bumi Resources Minerals", "sector": "Basic Materials"},
    {"symbol": "BUMI", "name": "Bumi Resources", "sector": "Energy"},
    {"symbol": "UNVR", "name": "Unilever Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "BRIS", "name": "Bank Syariah Indonesia", "sector": "Finance"},
    {"symbol": "ICBP", "name": "Indofood CBP Sukses Makmur", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "ANTM", "name": "Aneka Tambang", "sector": "Basic Materials"},
    {"symbol": "ISAT", "name": "Indosat Ooredoo Hutchison", "sector": "Infrastructures"},
    {"symbol": "CPIN", "name": "Charoen Pokphand Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "ADRO", "name": "Adaro Energy Indonesia", "sector": "Energy"},
    # Mid-large cap sharia stocks
    {"symbol": "INCO", "name": "Vale Indonesia", "sector": "Basic Materials"},
    {"symbol": "MDKA", "name": "Merdeka Copper Gold", "sector": "Basic Materials"},
    {"symbol": "KLBF", "name": "Kalbe Farma", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "PTBA", "name": "Bukit Asam", "sector": "Energy"},
    {"symbol": "SMGR", "name": "Semen Indonesia", "sector": "Basic Materials"},
    {"symbol": "INTP", "name": "Indocement Tunggal Prakarsa", "sector": "Basic Materials"},
    {"symbol": "MYOR", "name": "Mayora Indah", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "JPFA", "name": "Japfa Comfeed Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "EXCL", "name": "XL Axiata", "sector": "Infrastructures"},
    {"symbol": "JSMR", "name": "Jasa Marga", "sector": "Infrastructures"},
    # Infrastructure & Property sharia stocks
    {"symbol": "TBIG", "name": "Tower Bersama Infrastructure", "sector": "Infrastructures"},
    {"symbol": "TOWR", "name": "Sarana Menara Nusantara", "sector": "Infrastructures"},
    {"symbol": "WIKA", "name": "Wijaya Karya", "sector": "Infrastructures"},
    {"symbol": "WSKT", "name": "Waskita Karya", "sector": "Infrastructures"},
    {"symbol": "CTRA", "name": "Ciputra Development", "sector": "Property & Real Estate"},
    {"symbol": "SMRA", "name": "Summarecon Agung", "sector": "Property & Real Estate"},
    {"symbol": "BSDE", "name": "Bumi Serpong Damai", "sector": "Property & Real Estate"},
    {"symbol": "PWON", "name": "Pakuwon Jati", "sector": "Property & Real Estate"},
    # Consumer & Healthcare sharia stocks
    {"symbol": "SIDO", "name": "Industri Jamu dan Farmasi Sido Muncul", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "MIKA", "name": "Mitra Keluarga Karyasehat", "sector": "Healthcare"},
    {"symbol": "ERAA", "name": "Erajaya Swasembada", "sector": "Consumer Cyclicals"},
    {"symbol": "MAPI", "name": "Mitra Adiperkasa", "sector": "Consumer Cyclicals"},
    {"symbol": "ACES", "name": "Ace Hardware Indonesia", "sector": "Consumer Cyclicals"},
    {"symbol": "AMRT", "name": "Sumber Alfaria Trijaya", "sector": "Consumer Cyclicals"},
    # Energy & Mining sharia stocks
    {"symbol": "MEDC", "name": "Medco Energi Internasional", "sector": "Energy"},
    {"symbol": "HRUM", "name": "Harum Energy", "sector": "Energy"},
    {"symbol": "ITMG", "name": "Indo Tambangraya Megah", "sector": "Energy"},
    {"symbol": "AKRA", "name": "AKR Corporindo", "sector": "Energy"},
    {"symbol": "ESSA", "name": "Surya Esa Perkasa", "sector": "Energy"},
    {"symbol": "PGAS", "name": "Perusahaan Gas Negara", "sector": "Energy"},
    {"symbol": "TINS", "name": "Timah", "sector": "Basic Materials"},
    # Technology & Media sharia stocks
    {"symbol": "EMTK", "name": "Elang Mahkota Teknologi", "sector": "Technology"},
    {"symbol": "BUKA", "name": "Bukalapak.com", "sector": "Technology"},
    {"symbol": "MNCN", "name": "Media Nusantara Citra", "sector": "Consumer Cyclicals"},
    {"symbol": "SCMA", "name": "Surya Citra Media", "sector": "Consumer Cyclicals"},
    # Paper & Materials sharia stocks
    {"symbol": "INKP", "name": "Indah Kiat Pulp & Paper", "sector": "Basic Materials"},
    {"symbol": "TKIM", "name": "Pabrik Kertas Tjiwi Kimia", "sector": "Basic Materials"},
    # Additional liquid sharia stocks
    {"symbol": "BTPS", "name": "Bank BTPN Syariah", "sector": "Finance"},
    {"symbol": "SRTG", "name": "Saratoga Investama Sedaya", "sector": "Finance"},
    {"symbol": "MLPT", "name": "Multipolar Technology", "sector": "Technology"},
    {"symbol": "KPIG", "name": "MNC Land", "sector": "Property & Real Estate"},
    {"symbol": "BMTR", "name": "Global Mediacom", "sector": "Consumer Cyclicals"},
    {"symbol": "LSIP", "name": "PP London Sumatra Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "AALI", "name": "Astra Agro Lestari", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "SSMS", "name": "Sawit Sumbermas Sarana", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "SILO", "name": "Siloam International Hospitals", "sector": "Healthcare"},
    {"symbol": "AUTO", "name": "Astra Otoparts", "sector": "Consumer Cyclicals"},
    {"symbol": "SMDR", "name": "Samudera Indonesia", "sector": "Transportation & Logistics"},
    # Note: INKA removed (delisted from Yahoo Finance)
]

# Other notable IDX stocks
OTHER_IDX_STOCKS = [
    {"symbol": "AALI", "name": "Astra Agro Lestari", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "ADMR", "name": "Adaro Minerals Indonesia", "sector": "Basic Materials"},
    {"symbol": "ADMF", "name": "Adira Dinamika Multi Finance", "sector": "Finance"},
    {"symbol": "AGII", "name": "Aneka Gas Industri", "sector": "Industrials"},
    {"symbol": "ANJT", "name": "Austindo Nusantara Jaya", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "APLN", "name": "Agung Podomoro Land", "sector": "Property & Real Estate"},
    {"symbol": "ARTO", "name": "Bank Jago", "sector": "Finance"},
    {"symbol": "ASRI", "name": "Alam Sutera Realty", "sector": "Property & Real Estate"},
    {"symbol": "AUTO", "name": "Astra Otoparts", "sector": "Consumer Cyclicals"},
    {"symbol": "BDMN", "name": "Bank Danamon Indonesia", "sector": "Finance"},
    {"symbol": "BJBR", "name": "Bank Pembangunan Daerah Jawa Barat dan Banten", "sector": "Finance"},
    {"symbol": "BNGA", "name": "Bank CIMB Niaga", "sector": "Finance"},
    {"symbol": "BTPS", "name": "Bank BTPN Syariah", "sector": "Finance"},
    {"symbol": "DMAS", "name": "Puradelta Lestari", "sector": "Property & Real Estate"},
    {"symbol": "DOID", "name": "Delta Dunia Makmur", "sector": "Energy"},
    {"symbol": "BREN", "name": "Barito Renewables Energy", "sector": "Energy"},
    {"symbol": "GGRM", "name": "Gudang Garam", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "GIAA", "name": "Garuda Indonesia", "sector": "Transportation & Logistics"},
    {"symbol": "HEXA", "name": "Hexindo Adiperkasa", "sector": "Industrials"},
    {"symbol": "INDY", "name": "Indika Energy", "sector": "Energy"},
    {"symbol": "KAEF", "name": "Kimia Farma", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "LPKR", "name": "Lippo Karawaci", "sector": "Property & Real Estate"},
    {"symbol": "LPPF", "name": "Matahari Department Store", "sector": "Consumer Cyclicals"},
    {"symbol": "LSIP", "name": "PP London Sumatra Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "MAIN", "name": "Malindo Feedmill", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "MEGA", "name": "Bank Mega", "sector": "Finance"},
    {"symbol": "MIKA", "name": "Mitra Keluarga Karyasehat", "sector": "Healthcare"},
    {"symbol": "MNCN", "name": "Media Nusantara Citra", "sector": "Consumer Cyclicals"},
    {"symbol": "NCKL", "name": "Trimegah Bangun Persada", "sector": "Basic Materials"},
    {"symbol": "NISP", "name": "Bank OCBC NISP", "sector": "Finance"},
    {"symbol": "PNBN", "name": "Bank Pan Indonesia", "sector": "Finance"},
    {"symbol": "PNLF", "name": "Panin Financial", "sector": "Finance"},
    {"symbol": "PWON", "name": "Pakuwon Jati", "sector": "Property & Real Estate"},
    {"symbol": "SCMA", "name": "Surya Citra Media", "sector": "Consumer Cyclicals"},
    {"symbol": "SIDO", "name": "Industri Jamu dan Farmasi Sido Muncul", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "SIMP", "name": "Salim Ivomas Pratama", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "SMDR", "name": "Samudera Indonesia", "sector": "Transportation & Logistics"},
    {"symbol": "SMRA", "name": "Summarecon Agung", "sector": "Property & Real Estate"},
    {"symbol": "SRIL", "name": "Sri Rejeki Isman", "sector": "Industrials"},
    {"symbol": "SSMS", "name": "Sawit Sumbermas Sarana", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "TINS", "name": "Timah", "sector": "Basic Materials"},
    {"symbol": "TKIM", "name": "Pabrik Kertas Tjiwi Kimia", "sector": "Basic Materials"},
    {"symbol": "TPIA", "name": "Chandra Asri Petrochemical", "sector": "Basic Materials"},
    {"symbol": "PTRO", "name": "Petrosea", "sector": "Energy"},
    {"symbol": "UNVR", "name": "Unilever Indonesia", "sector": "Consumer Non-Cyclicals"},
    {"symbol": "WIKA", "name": "Wijaya Karya", "sector": "Infrastructures"},
    {"symbol": "WSKT", "name": "Waskita Karya", "sector": "Infrastructures"},
    {"symbol": "WTON", "name": "Wijaya Karya Beton", "sector": "Infrastructures"},
]

def _build_all_stocks() -> list[dict[str, Any]]:
    """Build deduplicated static stock universe."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for stock in IDX30_STOCKS + LQ45_ADDITIONAL + JII70_STOCKS + OTHER_IDX_STOCKS:
        symbol = stock.get("symbol", "").upper().strip()
        name = stock.get("name", "").strip()
        sector = stock.get("sector", "Unknown").strip() or "Unknown"
        if not symbol or not name or symbol in seen:
            continue
        seen.add(symbol)
        result.append({"symbol": symbol, "name": name, "sector": sector})
    return result


# Combine all stocks (static fallback)
ALL_IDX_STOCKS = _build_all_stocks()


class DynamicStockUniverse:
    """Fetch IDX stock universe with multi-source fallback and local cache."""

    def _parse_idx_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse IDX response and normalize multi-format payloads."""
        stocks: list[dict[str, Any]] = []
        seen: set[str] = set()

        items = data.get("data", []) if isinstance(data, dict) else []
        if not items and isinstance(data, dict):
            items = data.get("Datas", [])
        if not items and isinstance(data, dict):
            items = data.get("result", [])

        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            symbol = str(
                item.get("KodeEmiten")
                or item.get("StockCode")
                or item.get("symbol")
                or item.get("code")
                or ""
            ).strip().upper()
            name = str(
                item.get("NamaEmiten")
                or item.get("StockName")
                or item.get("name")
                or ""
            ).strip()
            sector = str(
                item.get("Sektor")
                or item.get("SectorName")
                or item.get("sector")
                or "Unknown"
            ).strip() or "Unknown"

            if symbol and name and symbol not in seen:
                seen.add(symbol)
                stocks.append({"symbol": symbol, "name": name, "sector": sector})

        return stocks

    async def _fetch_idx_official(self) -> list[dict[str, Any]]:
        """Fetch stock list from IDX official endpoint using warmup session."""
        def _parse_json_response(resp: httpx.Response) -> dict[str, Any]:
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass

            raw = resp.content
            if raw[:2] == b"\x1f\x8b":
                try:
                    payload = json.loads(gzip.decompress(raw).decode("utf-8", errors="ignore"))
                    if isinstance(payload, dict):
                        return payload
                except Exception:
                    pass

            payload = json.loads(resp.text)
            if isinstance(payload, dict):
                return payload
            return {}

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=IDX_BROWSER_HEADERS,
        ) as client:
            try:
                await client.get(
                    "https://www.idx.co.id/id/data-pasar/data-saham/daftar-saham/",
                    timeout=10,
                )
            except Exception:
                pass

            for url in [IDX_STOCK_LIST_URL, IDX_STOCK_LIST_URL_ALT]:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    payload = _parse_json_response(resp)
                    stocks = self._parse_idx_response(payload)
                    if stocks:
                        return stocks
                except Exception as exc:
                    logger.warning("IDX URL %s failed: %s", url, exc)
                    continue

        raise ValueError("All IDX URLs failed")

    async def _fetch_via_yahoo(self) -> list[dict[str, Any]]:
        """Fetch IDX universe candidates via Yahoo screener pagination."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }
        stocks: list[dict[str, Any]] = []
        seen: set[str] = set()
        start = 0

        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
            for template in YAHOO_SCREENER_URLS:
                start = 0
                while True:
                    url = template.format(start=start)
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as exc:
                        logger.warning("Yahoo URL %s failed: %s", url, exc)
                        break

                    finance = data.get("finance", {}) if isinstance(data, dict) else {}
                    result = finance.get("result", [{}])
                    first = result[0] if isinstance(result, list) and result else {}
                    quotes = first.get("quotes", []) if isinstance(first, dict) else []

                    if not quotes:
                        break

                    for quote in quotes:
                        if not isinstance(quote, dict):
                            continue
                        raw_symbol = str(quote.get("symbol", "")).strip()
                        exchange = str(quote.get("exchange", "")).upper()
                        symbol = ""
                        if raw_symbol.endswith(".JK"):
                            symbol = raw_symbol.replace(".JK", "").strip().upper()
                        elif exchange in {"JKT", "JAK", "JAKARTA"} and raw_symbol:
                            symbol = raw_symbol.strip().upper()
                        if not symbol:
                            continue
                        name = str(
                            quote.get("longName")
                            or quote.get("shortName")
                            or symbol
                        ).strip()
                        sector = str(quote.get("sector") or "Unknown").strip() or "Unknown"

                        if symbol and symbol not in seen:
                            seen.add(symbol)
                            stocks.append({"symbol": symbol, "name": name, "sector": sector})

                    total = int(first.get("total", 0) or 0) if isinstance(first, dict) else 0
                    start += len(quotes)
                    if start >= total or not quotes:
                        break

        if not stocks:
            raise ValueError("Yahoo screener returned empty")

        logger.info("Yahoo screener: %d stocks fetched", len(stocks))
        return stocks

    async def _fetch_via_yfinance_validate(self) -> list[dict[str, Any]]:
        """Bulk-validate IDX candidates via yfinance.download()."""
        import pandas as pd
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor

        all_candidates: list[str] = list(
            dict.fromkeys([s["symbol"] for s in ALL_IDX_STOCKS] + KNOWN_IDX_PREFIXES)
        )
        yf_tickers = [f"{sym}.JK" for sym in all_candidates]
        static_map = {s["symbol"]: s for s in ALL_IDX_STOCKS}

        def _sync_validate() -> list[dict[str, Any]]:
            stocks: list[dict[str, Any]] = []
            seen: set[str] = set()
            batch_size = 100

            for i in range(0, len(yf_tickers), batch_size):
                batch = yf_tickers[i: i + batch_size]
                try:
                    df = yf.download(
                        tickers=" ".join(batch),
                        period="5d",
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=True,
                        progress=False,
                        threads=True,
                    )
                    if df is None or df.empty:
                        continue

                    if isinstance(df.columns, pd.MultiIndex):
                        level0 = {str(v) for v in df.columns.get_level_values(0)}
                        level1 = {str(v) for v in df.columns.get_level_values(1)}

                        # yfinance can return either:
                        # 1) level0=ticker, level1=field (group_by=ticker)
                        # 2) level0=field,  level1=ticker
                        if "Close" in level0:
                            tickers = [t for t in level1 if str(t).endswith(".JK")]
                            for ticker in tickers:
                                try:
                                    close = df["Close"][ticker]
                                    if close.dropna().empty:
                                        continue
                                except Exception:
                                    continue
                                sym = str(ticker).replace(".JK", "").upper()
                                if sym and sym not in seen:
                                    seen.add(sym)
                                    static = static_map.get(sym, {})
                                    stocks.append({
                                        "symbol": sym,
                                        "name": static.get("name", sym),
                                        "sector": static.get("sector", "Unknown"),
                                    })
                        else:
                            tickers = [t for t in level0 if str(t).endswith(".JK")]
                            for ticker in tickers:
                                try:
                                    close = df[ticker]["Close"]
                                    if close.dropna().empty:
                                        continue
                                except Exception:
                                    continue
                                sym = str(ticker).replace(".JK", "").upper()
                                if sym and sym not in seen:
                                    seen.add(sym)
                                    static = static_map.get(sym, {})
                                    stocks.append({
                                        "symbol": sym,
                                        "name": static.get("name", sym),
                                        "sector": static.get("sector", "Unknown"),
                                    })
                    else:
                        if len(batch) == 1:
                            sym = batch[0].replace(".JK", "").upper()
                            close = df.get("Close")
                            if close is not None and not close.dropna().empty and sym not in seen:
                                seen.add(sym)
                                static = static_map.get(sym, {})
                                stocks.append({
                                    "symbol": sym,
                                    "name": static.get("name", sym),
                                    "sector": static.get("sector", "Unknown"),
                                })
                except Exception as exc:
                    logger.warning("yfinance batch %d-%d failed: %s", i, i + batch_size, exc)
                    continue

            return stocks

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            stocks = await loop.run_in_executor(pool, _sync_validate)

        if len(stocks) < 50:
            raise ValueError(f"yfinance bulk validate: only {len(stocks)} valid tickers")

        logger.info("yfinance bulk validate: %d stocks confirmed", len(stocks))
        return stocks

    def _cache_valid(self) -> bool:
        if not UNIVERSE_CACHE_FILE.exists():
            return False
        mtime = datetime.fromtimestamp(UNIVERSE_CACHE_FILE.stat().st_mtime)
        return datetime.now() - mtime < timedelta(days=CACHE_TTL_DAYS)

    def _load_cache(self) -> list[dict[str, Any]]:
        raw = json.loads(UNIVERSE_CACHE_FILE.read_text(encoding="utf-8"))
        stocks = raw.get("stocks", []) if isinstance(raw, dict) else []
        result: list[dict[str, Any]] = []
        for stock in stocks:
            symbol = str(stock.get("symbol", "")).upper().strip()
            name = str(stock.get("name", "")).strip()
            sector = str(stock.get("sector", "Unknown")).strip() or "Unknown"
            if symbol and name:
                result.append({"symbol": symbol, "name": name, "sector": sector})
        return result

    def _save_cache(self, stocks: list[dict[str, Any]], source: str) -> None:
        UNIVERSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": datetime.now().isoformat(),
            "source": source,
            "count": len(stocks),
            "stocks": stocks,
        }
        UNIVERSE_CACHE_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _cache_info(self) -> dict[str, Any]:
        """Return cache metadata for CLI status."""
        if not UNIVERSE_CACHE_FILE.exists():
            return {"exists": False}
        try:
            raw = json.loads(UNIVERSE_CACHE_FILE.read_text(encoding="utf-8"))
            return {
                "exists": True,
                "count": raw.get("count", 0),
                "source": raw.get("source", "unknown"),
                "fetched_at": raw.get("fetched_at", "unknown"),
                "valid": self._cache_valid(),
            }
        except Exception:
            return {"exists": True, "valid": False, "error": "corrupt cache"}

    async def get_all_stocks(self) -> list[dict[str, Any]]:
        """Return universe: cache -> IDX -> Yahoo -> yfinance validate -> static."""
        if self._cache_valid():
            try:
                cached = self._load_cache()
                if cached:
                    logger.debug("Universe from cache: %d stocks", len(cached))
                    return cached
            except Exception as exc:
                logger.warning("Cache read failed: %s", exc)

        for source_name, fetch_fn, source_key in [
            ("IDX API", self._fetch_idx_official, "idx_official"),
            ("Yahoo Screener", self._fetch_via_yahoo, "yahoo_screener"),
            ("yfinance Validate", self._fetch_via_yfinance_validate, "yfinance_validate"),
        ]:
            try:
                stocks = await fetch_fn()
                if stocks:
                    self._save_cache(stocks, source=source_key)
                    logger.info("Universe from %s: %d stocks", source_name, len(stocks))
                    return stocks
            except Exception as exc:
                logger.warning("%s failed: %s", source_name, exc)

        logger.warning("All sources failed, using static: %d stocks", len(ALL_IDX_STOCKS))
        return ALL_IDX_STOCKS.copy()

    async def force_refresh(self) -> dict[str, Any]:
        """Force refresh universe: clear cache then try all sources in order."""
        if UNIVERSE_CACHE_FILE.exists():
            UNIVERSE_CACHE_FILE.unlink()

        sources = [
            ("IDX Official API", self._fetch_idx_official, "idx_official"),
            ("Yahoo Finance Screener", self._fetch_via_yahoo, "yahoo_screener"),
            ("yfinance Bulk Validate", self._fetch_via_yfinance_validate, "yfinance_validate"),
        ]

        for source_name, fetch_fn, source_key in sources:
            try:
                stocks = await fetch_fn()
                if len(stocks) < 150:
                    logger.warning(
                        "%s: only %d stocks, trying next source",
                        source_name, len(stocks),
                    )
                    continue
                self._save_cache(stocks, source=source_key)
                logger.info("Universe from %s: %d stocks", source_name, len(stocks))
                return {"success": True, "source": source_name, "count": len(stocks)}
            except Exception as exc:
                logger.warning("%s failed: %s", source_name, exc)

        try:
            stocks = await self._fetch_via_yfinance_validate()
            self._save_cache(stocks, source="yfinance_validate_no_threshold")
            return {
                "success": True,
                "source": "yfinance Bulk Validate (no threshold)",
                "count": len(stocks),
            }
        except Exception as exc:
            logger.error("yfinance validate also failed: %s", exc)

        return {"success": False, "source": "static_fallback", "count": len(ALL_IDX_STOCKS)}

    async def _fetch_via_yfinance_indices(self) -> list[dict[str, Any]]:
        """Backward-compat alias, use bulk validate implementation."""
        return await self._fetch_via_yfinance_validate()

    def get_all_stocks_sync(self) -> list[dict[str, Any]]:
        """Sync wrapper for non-async contexts (cache first, fallback static)."""
        try:
            if self._cache_valid():
                return self._load_cache()
        except Exception:
            pass
        return ALL_IDX_STOCKS.copy()


class IDXStockDatabase:
    """Local database for IDX stock listings with search capabilities."""

    def __init__(self, stocks: list[dict[str, Any]] | None = None):
        """Initialize the stock database."""
        source = stocks if stocks is not None else ALL_IDX_STOCKS
        self._stocks: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for stock in source:
            symbol = str(stock.get("symbol", "")).upper().strip()
            name = str(stock.get("name", "")).strip()
            sector = str(stock.get("sector", "Unknown")).strip() or "Unknown"
            if not symbol or not name or symbol in seen:
                continue
            seen.add(symbol)
            self._stocks[symbol] = {"symbol": symbol, "name": name, "sector": sector}
        self._name_index = self._build_name_index()

    @classmethod
    async def from_dynamic(cls) -> "IDXStockDatabase":
        """Create stock database from dynamic IDX universe."""
        universe = get_stock_universe()
        stocks = await universe.get_all_stocks()
        return cls(stocks=stocks)

    def _build_name_index(self) -> dict[str, str]:
        """Build index of stock names to symbols."""
        index = {}
        for stock in self._stocks.values():
            # Add full name
            name_lower = stock["name"].lower()
            index[name_lower] = stock["symbol"]

            # Add individual words from name
            for word in name_lower.split():
                if len(word) > 2:
                    if word not in index:
                        index[word] = stock["symbol"]

        return index

    def get_stock(self, symbol: str) -> dict[str, Any] | None:
        """Get stock info by symbol.

        Args:
            symbol: Stock symbol (e.g., BBCA)

        Returns:
            Stock info dict or None
        """
        symbol = symbol.upper().replace(".JK", "")
        return self._stocks.get(symbol)

    def get_idx30_stocks(self) -> list[dict[str, Any]]:
        """Get all IDX30 stocks."""
        return IDX30_STOCKS.copy()

    def get_lq45_stocks(self) -> list[dict[str, Any]]:
        """Get all LQ45 stocks."""
        return (IDX30_STOCKS + LQ45_ADDITIONAL).copy()

    def get_jii70_stocks(self) -> list[dict[str, Any]]:
        """Get all JII70 stocks (Jakarta Islamic Index 70)."""
        return JII70_STOCKS.copy()

    def get_all_stocks(self) -> list[dict[str, Any]]:
        """Get all known IDX stocks."""
        return list(self._stocks.values())

    def get_stocks_by_sector(self, sector: str) -> list[dict[str, Any]]:
        """Get stocks by sector.

        Args:
            sector: Sector name

        Returns:
            List of stocks in sector
        """
        return [s for s in self._stocks.values() if s["sector"].lower() == sector.lower()]

    def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search for stocks by symbol or name.

        Uses fuzzy matching to find stocks matching the query.

        Args:
            query: Search query (symbol or name)
            limit: Maximum results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of matching stocks with scores
        """
        if not query:
            return []

        query = query.strip().upper()
        query_lower = query.lower()
        results = []

        # First: Exact symbol match
        if query in self._stocks:
            stock = self._stocks[query].copy()
            stock["score"] = 1.0
            stock["match_type"] = "exact_symbol"
            return [stock]

        # Second: Symbol prefix match
        for symbol, stock in self._stocks.items():
            if symbol.startswith(query):
                result = stock.copy()
                result["score"] = 0.9
                result["match_type"] = "symbol_prefix"
                results.append(result)

        # Third: Name contains query
        for stock in self._stocks.values():
            if query_lower in stock["name"].lower():
                if not any(r["symbol"] == stock["symbol"] for r in results):
                    result = stock.copy()
                    result["score"] = 0.7
                    result["match_type"] = "name_contains"
                    results.append(result)

        # Fourth: Fuzzy match on names
        for stock in self._stocks.values():
            if any(r["symbol"] == stock["symbol"] for r in results):
                continue

            # Check symbol similarity
            symbol_score = SequenceMatcher(None, query, stock["symbol"]).ratio()
            name_score = SequenceMatcher(None, query_lower, stock["name"].lower()).ratio()

            best_score = max(symbol_score, name_score)
            if best_score >= min_score:
                result = stock.copy()
                result["score"] = best_score
                result["match_type"] = "fuzzy"
                results.append(result)

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


# Singleton instance
_db: IDXStockDatabase | None = None
_universe: DynamicStockUniverse | None = None


def get_stock_universe() -> DynamicStockUniverse:
    """Get singleton dynamic stock universe fetcher."""
    global _universe
    if _universe is None:
        _universe = DynamicStockUniverse()
    return _universe


def get_stock_database() -> IDXStockDatabase:
    """Get singleton stock database instance."""
    global _db
    if _db is None:
        try:
            stocks = get_stock_universe().get_all_stocks_sync()
            _db = IDXStockDatabase(stocks=stocks)
        except Exception:
            _db = IDXStockDatabase()
    return _db


def search_stocks(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for stocks by symbol or name."""
    return get_stock_database().search(query, limit)


def get_stock_info(symbol: str) -> dict[str, Any] | None:
    """Get stock info by symbol."""
    return get_stock_database().get_stock(symbol)


def get_idx30_list() -> list[str]:
    """Get list of IDX30 symbols."""
    return [s["symbol"] for s in IDX30_STOCKS]


def get_lq45_list() -> list[str]:
    """Get list of LQ45 symbols."""
    return [s["symbol"] for s in IDX30_STOCKS + LQ45_ADDITIONAL]


def get_jii70_list() -> list[str]:
    """Get list of JII70 symbols (Jakarta Islamic Index 70)."""
    return [s["symbol"] for s in JII70_STOCKS]
