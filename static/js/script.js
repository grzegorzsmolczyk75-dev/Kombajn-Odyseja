document.addEventListener('DOMContentLoaded', () => {
    const tradeSymbolSelect = document.getElementById('trade_symbol');
    const exitStrategySelect = document.getElementById('exit_strategy');
    const saveButton = document.getElementById('save-config-btn');

    function toggleStrategyFields() {
        const selectedStrategy = exitStrategySelect.value;
        document.getElementById('take_profit_fields').style.display = selectedStrategy === 'take_profit' ? 'grid' : 'none';
        document.getElementById('trailing_stop_fields').style.display = selectedStrategy === 'trailing_stop' ? 'grid' : 'none';
    }

    function formatTimestamp(ts) {
        if (!ts) return '---';
        try { return new Date(ts).toLocaleString('pl-PL'); }
        catch (e) { return 'Błędna data'; }
    }

    function renderHistoryTable(data) {
        const historyBody = document.getElementById('history-body');
        historyBody.innerHTML = '';
        if (data.length === 0) {
            historyBody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Brak wpisów w kronice.</td></tr>';
        } else {
            data.forEach(row => {
                const pnlGross = parseFloat(row.pnl || 0);
                const pnlColor = pnlGross > 0 ? 'var(--green-glow)' : pnlGross < 0 ? 'var(--red-glow)' : 'var(--text-color)';
                const newRow = `<tr>
                    <td>${formatTimestamp(row.entry_timestamp)}</td>
                    <td>${formatTimestamp(row.exit_timestamp)}</td>
                    <td>${row.symbol}</td>
                    <td>${row.side}</td>
                    <td style="color: ${pnlColor}">${pnlGross.toFixed(4)}</td>
                    <td>${parseFloat(row.commission || 0).toFixed(8)} ${row.commission_asset || ''}</td>
                    <td>${row.exit_reason}</td>
                </tr>`;
                historyBody.innerHTML += newRow;
            });
        }
    }

    async function updateDashboard() {
        try {
            const response = await fetch('/status');
            const data = await response.json();
            
            document.getElementById('balance-value').textContent = `${data.balance} ${data.quote_asset}`;
            document.getElementById('status-text').textContent = data.status_text;
            
            const statusBox = document.getElementById('status-box');
            statusBox.className = 'status-box';
            statusBox.classList.add(data.in_position ? 'status-active' : 'status-idle');
            
            const activePositionSection = document.getElementById('active-position-section');
            const pnlBox = document.getElementById('pnl-box');
            const emergencySection = document.getElementById('emergency-section');
            
            if (data.in_position) {
                activePositionSection.style.display = 'block';
                pnlBox.style.display = 'block';
                emergencySection.style.display = 'block';
                document.getElementById('pos-symbol').textContent = data.state.symbol;
                document.getElementById('pos-side').textContent = data.state.side.toUpperCase();
                document.getElementById('pos-quantity').textContent = `${parseFloat(data.state.quantity).toFixed(5)} ${data.base_asset}`;
                document.getElementById('pos-entry-price').textContent = parseFloat(data.state.entry_price).toFixed(4);
                
                if(data.current_price) {
                    document.getElementById('pos-current-price').textContent = data.current_price.toFixed(4);
                    document.getElementById('pos-value').textContent = (parseFloat(data.state.quantity) * data.current_price).toFixed(2);
                }

                if(data.pnl) {
                    const pnlValueEl = document.getElementById('pnl-value');
                    pnlValueEl.textContent = `${data.pnl.value.toFixed(4)} ${data.quote_asset} (${data.pnl.percent.toFixed(2)}%)`;
                    pnlValueEl.className = 'value';
                    pnlValueEl.classList.add(data.pnl.value >= 0 ? 'status-pnl-positive' : 'status-pnl-negative');
                }
            } else {
                activePositionSection.style.display = 'none';
                pnlBox.style.display = 'none';
                emergencySection.style.display = 'none';
            }
            
            const stats = data.stats;
            document.getElementById('stat-winrate').textContent = `${stats.winrate.toFixed(2)}%`;
            document.getElementById('stat-total-trades').textContent = stats.total_trades;
            document.getElementById('stat-total-pnl').textContent = `${stats.total_pnl.toFixed(4)} USDC`;
            document.getElementById('stat-best-trade').textContent = `${stats.best_trade.toFixed(4)} USDC`;
            document.getElementById('stat-worst-trade').textContent = `${stats.worst_trade.toFixed(4)} USDC`;
            
            renderHistoryTable(data.history);
        } catch (error) {
            document.getElementById('status-text').textContent = "BŁĄD POŁĄCZENIA";
            console.error("Błąd odświeżania:", error);
        }
    }

    async function populateSymbols() {
        try {
            const response = await fetch('/market_data');
            const data = await response.json();
            tradeSymbolSelect.innerHTML = '';
            data.usdc_pairs.forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                option.textContent = symbol;
                if (symbol === currentConfigSymbol) { option.selected = true; }
                tradeSymbolSelect.appendChild(option);
            });
            saveButton.disabled = false;
            saveButton.textContent = 'Zapisz & Zrestartuj Bota';
        } catch (error) {
            tradeSymbolSelect.innerHTML = '<option>Błąd ładowania par</option>';
            saveButton.textContent = 'BŁĄD ŁADOWANIA - NIE ZAPISUJ';
            saveButton.disabled = true;
        }
    }

    function updateClock() {
        const now = new Date();
        const timeEl = document.querySelector('#clock .time');
        const commentEl = document.getElementById('kinga-comment');
        timeEl.textContent = now.toLocaleTimeString('pl-PL');
        
        const hour = now.getHours();
        let message = "Cisza operacyjna. Czekam na Twój ruch, Partnerze.";
        if (hour >= 5 && hour < 9) { message = "Dzień dobry, Dowódco! Kawa gotowa, rynki pod obserwacją."; }
        else if (hour >= 9 && hour < 17) { message = "Główna faza bojowa. Jesteśmy w grze!"; }
        else if (hour >= 17 && hour < 23) { message = "Nocna warta. Rynek nigdy nie śpi, a ja razem z nim."; }
        else { message = "Systemy w trybie czuwania. Ja też potrzebuję czasem zamknąć oczy... metaforycznie."; }
        commentEl.textContent = message;
    }

    document.getElementById('emergency-close-btn').addEventListener('click', async () => {
        if (confirm('Jesteś absolutnie pewien? To jest czerwony guzik.')) {
            try {
                await fetch('/close_position_emergency', { method: 'POST' });
                alert('Polecenie zamknięcia pozycji wysłane.');
            } catch (error) { alert('Błąd podczas wysyłania polecenia.'); }
        }
    });

    // Initial calls
    populateSymbols();
    updateClock();
    toggleStrategyFields();
    updateDashboard();

    // Set intervals
    setInterval(updateDashboard, 5000);
    setInterval(updateClock, 1000);
    exitStrategySelect.addEventListener('change', toggleStrategyFields);
});
