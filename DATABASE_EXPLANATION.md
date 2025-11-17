# Database System Explanation

## Technical Explanation

### Architecture
We use **SQLite** as our database system. SQLite is a file-based database that stores all data in a single file (`pnl_trades.db`). It's lightweight, fast, and perfect for our use case.

### Database File Location
- **Railway**: `/tmp/pnl_trades.db` (persistent across deploys if `/tmp` is mounted)
- **Local**: `pnl_trades.db` in the project root
- **Auto-detection**: The system checks `/data`, `/persist`, `/tmp` in that order

### Database Structure
Our single database file contains **three tables**:

1. **`trades`** - Completed trade records
   - Stores: strategy, side, entry/exit prices, PnL, timestamps, exit reasons
   - Used for: PnL analysis, performance tracking, historical analysis

2. **`positions`** - Open position state
   - Stores: strategy, side, entry price, size, stop loss, take profit, entry time
   - Used for: Recovering positions after deploys

3. **`candles`** - OHLCV candle data
   - Stores: strategy, market, open_time, OHLCV data
   - Used for: Recovering candle history after deploys (breakout strategy)

### How It Works

#### Write-Ahead Logging (WAL)
- SQLite uses **WAL mode** for better concurrency
- Changes are written to a separate log file first
- Then committed to the main database
- This allows multiple readers while one writer is active

#### Transactions
- Each write operation is wrapped in a **transaction**
- If something fails, the transaction is **rolled back** (changes are undone)
- If successful, the transaction is **committed** (changes are saved)

#### Persistence
- Data is written to disk immediately on commit
- On Railway, the file persists in `/tmp` (if mounted as a volume)
- If the container restarts, the database file remains intact

### Performance
- **Indexes**: We create indexes on frequently queried columns (strategy, market, timestamps)
- **Batch operations**: Multiple writes can be batched for efficiency
- **Connection pooling**: Single connection shared across all operations (with locks)

### Backup System
- **Local backups**: Hourly backups to `/tmp/backups/` (configurable)
- **Retention**: Keeps last N backups (configurable, default: 10)
- **Format**: SQLite database files (can be restored directly)

---

## ELI5 (Explain Like I'm 5)

### What is a Database?
Imagine a **filing cabinet** where you keep all your important papers organized.

- **Our filing cabinet** = `pnl_trades.db` (one file)
- **Drawers** = Tables (trades, positions, candles)
- **Folders** = Rows (each trade, position, or candle)
- **Labels** = Indexes (help you find things fast)

### How Does It Work?

**When we make a trade:**
1. We write it down on a piece of paper (a "row")
2. Put it in the "trades" drawer
3. The filing cabinet saves it permanently

**When we deploy (restart the bot):**
1. The bot opens the filing cabinet
2. Looks in the "positions" drawer: "Oh, I have an open position!"
3. Looks in the "candles" drawer: "Oh, I have 47 candles saved!"
4. Picks up exactly where it left off

### Why Does It Survive Deploys?

**Think of it like this:**
- **Memory (RAM)** = Your desk (temporary, gets cleared when you leave)
- **Database (disk)** = The filing cabinet (permanent, stays there)

When the bot restarts:
- Everything on the **desk** (memory) is gone
- Everything in the **filing cabinet** (database) is still there
- The bot just opens the cabinet and reads what it saved before

### The Three Drawers

1. **Trades Drawer** 📊
   - "I made a trade, made $5, here's the receipt"
   - Used to see how much money we've made

2. **Positions Drawer** 📍
   - "I'm currently holding 10 shares, bought at $100"
   - Used to remember what we're holding when we restart

3. **Candles Drawer** 🕯️
   - "Here's the price history: $100, $101, $99, $102..."
   - Used to remember price patterns when we restart

### Why One File?

Instead of three separate filing cabinets, we use **one cabinet with three drawers**. This is simpler:
- One place to backup
- One place to manage
- Faster (everything in one place)

### What Happens on Railway?

On Railway (cloud):
- The filing cabinet lives in `/tmp/pnl_trades.db`
- Railway keeps this file even when the bot restarts
- It's like having a **safe deposit box** that never gets cleared

---

## Key Takeaways

✅ **One database file** = One filing cabinet
✅ **Three tables** = Three drawers
✅ **Survives deploys** = Filing cabinet stays, desk gets cleared
✅ **Fast queries** = Indexes help find things quickly
✅ **Safe writes** = Transactions ensure nothing gets lost
✅ **Backups** = Copies of the filing cabinet made regularly

