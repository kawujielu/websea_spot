# TradFi 现货 · 充提与对冲对比

## 1. 核心问题：都叫「股票」，为什么规则不同？

**「TradFi」是 App 里的一个分区名，不等于「都能提币」。**  
同一交易所里，标注为股票/Stock 的产品，可能分属 **完全不同的产品线**：

| 产品线 | 在哪看到 | 本质 | 链上充提 | 跨所对冲 |
|--------|---------|------|---------|---------|
| **A · CEX Spot 股票 token** | 现货区 / Ondo Zone / xStocks Zone | 真 token，有链上合约 | ✅ | ✅ |
| **B · TradFi Tab 股票 token** | Bitget → TradFi → Stock tokens | Ondo token，**平台托管** | ❌ | ❌ |
| **C · CFD 等 TradFi 衍生品** | Bitget → TradFi → CFD (MT5) | **不是 token**，是差价合约 | ❌ | ❌ |

**Bitget 最容易混淆：** 首页 **TradFi** 和 **现货** 里都有 NVIDIA「股票」，但一个是 B 类（NVDAon），一个是 A 类（NVDAON），**同名不同货、不可互转**。

**Gate 相对清晰：** 没有 Bitget 式 TradFi Tab；股票 token 分 **Ondo Zone** 和 **xStocks Zone** 两个现货专区，**官方均支持充提**（但发行方不同，符号不同，不能混用）。

---

## 2. Bitget：三种「TradFi/股票」产品对比

### 总表

| 类型 | 入口 | 符号示例 | 发行方 | 是否现货 token | 充币 | 提币 | 跨所对冲 |
|------|------|---------|--------|---------------|------|------|---------|
| **A · Spot 股票 token** | 现货 → `NVDAON/USDT` | 大写 **ON** | Ondo | ✅ | ✅ | ✅ 24/7 | ✅ |
| **B · TradFi 股票 token** | TradFi → **Stock tokens** | 小写 **on** | Ondo | ✅（平台内） | ❌ | ❌ | ❌ |
| **C · TradFi CFD** | TradFi → **CFD** (MT5) | XAUUSD 等 | 无 token | ❌ | — | 只能提 USDT | ❌ |

> B 与 A 底层同为 Ondo 1:1 背书，但 **Bitget 对 TradFi Tab 做了托管锁仓，不允许提出**。  
> C 根本不是 token，只是 USDT 保证金下的价格敞口，**与 Ondo 无关**。

### A 类 · ✅ 能提币对冲（15 对，走「现货」）

| 符号 | 标的 |
|------|------|
| NVDAON、TSLAON、AAPLON、GOOGLON、MSFTON、AMZNON、METAON、AMDON | 股票 |
| SPYON、IVVON、QQQON、IWMON、ITOTON | ETF |
| IAUON、SLVON | 商品 |

### B 类 · ❌ 不能提币（15 对，走「TradFi → Stock tokens」）

与上表 **一一对应**，符号为小写 on：`NVDAon`、`TSLAon`、`AAPLon`…  
UI 上明确标注为 **Stock tokens / 股票代币**，但属于 **平台内账本**，只能在本 Tab 买卖。

### C 类 · ❌ 不是 token（TradFi → CFD）

黄金、外汇、股指等 MT5 差价合约；**没有 AAPLON/NVDAon 这类符号**，无法提股票 token，只能平仓后提 USDT。

---

## 3. Gate：两种现货股票 token 对比

Gate **没有** Bitget 那种 TradFi Tab 双轨；股票 token 都在 **Spot 现货区**，分两个 Zone：

| 类型 | 入口 | 符号规则 | 发行方 | 充提 | 跨所对冲 |
|------|------|---------|--------|------|---------|
| **Ondo Zone** | Spot → Ondo Zone | 大写 **ON**（AAPLON） | Ondo GM | ✅ | ✅ 与 Bitget Spot ON 符号一致的可互转 |
| **xStocks Zone** | Spot → xStocks | 大写 **X**（TSLAX、AAPLX） | Backed xStock | ✅ | ⚠️ 符号不同，**不能**与 Ondo ON 直接互转 |

### Ondo Zone · ✅ 全部可提（26 对）

AAPLON、TSLAON、NVDAON、MSFTON、AMZNON、GOOGLON、METAON、AVGOON、BABAON、COINON、CRCLON、CSCOON、HOODON、LLYON、MAON、MCDON、MSTRON、NFLXON、PEPON、PLTRON、UNHON、SBETON、ABTON、ACNON、SPYON、QQQON

### xStocks Zone · ✅ 可提，但是另一套 token（Backed，非 Ondo）

首批：TSLAX、AAPLX、GOOGLX、NVDAX、METAX、COINX、HOODX、CRCLX 等（Solana SPL / ERC-20）

**与 Ondo 的区别：**
- 发行方：Backed（瑞士） vs Ondo（BVI SPV）
- 符号：`TSLAX` ≠ `TSLAON`，**不能跨 Zone 互转**
- 对冲：xStocks 只能 xStocks↔xStocks 或链上 DEX；Ondo 只能 Ondo↔Ondo

---

## 4. 跨所可对冲的 Ondo 现货（Bitget Spot ↔ Gate Ondo）

符号一致、可提币互转的 **9 对**：

AAPLON、TSLAON、NVDAON、MSFTON、AMZNON、GOOGLON、METAON、SPYON、QQQON

**仅 Bitget Spot 有：** AMDON、IVVON、IWMON、ITOTON、IAUON、SLVON  
**仅 Gate Ondo 有：** AVGOON、BABAON、COINON、CRCLON、CSCOON、HOODON、LLYON、MAON、MCDON、MSTRON、NFLXON、PEPON、PLTRON、UNHON、SBETON、ABTON、ACNON

---

## 5. 提币决策

| 你的目标 | Bitget 怎么买 | Gate 怎么买 |
|---------|--------------|------------|
| **提币 + 跨所现货对冲** | 走 **现货** `XXXON`，**不要** TradFi Tab | 走 **Ondo Zone** `XXXON` |
| **只做平台内买卖** | TradFi Stock tokens 也行，但 **提不出** | 任意 Zone 现货均可 |
| **对标 Ondo 做市** | 只用 Spot `XXXON` | 只用 Ondo Zone `XXXON` |
| **Backed xStock** | Bitget 暂无 | xStocks Zone `XXX X` |

---

## 6. 买前 3 条确认

1. **Bitget：看入口，不看名字** — 「TradFi 里的股票」≠ 「现货里的股票」  
2. **看符号后缀** — `ON`（Ondo 可提 Spot）、`on`（Bitget TradFi 不可提）、`X`（Backed xStock）  
3. **提币以 App 资产页 Withdraw 开关为准**

---

## 参考

- [Bitget NVDAon vs NVDAON（含 No withdrawals）](https://www.bitget.com/academy/how-to-trade-nvidia-stock-using-usdt-on-bitget-2026-guide)
- [Bitget TradFi 产品线（Stock tokens / CFD / Perps）](https://www.bitget.com/academy/how-to-trade-stocks-and-crypto-on-bitget-2026-guide)
- [Gate Ondo 26 对公告](https://www.gate.com/announcements/article/46930)
- [Gate xStocks 上线（含 TSLAX 充提）](https://www.gate.com/announcements/article/45926)
