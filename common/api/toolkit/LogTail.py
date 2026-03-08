from common.api.enums.ApiUrl import ApiUrl


LogTail: str = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <link rel="icon" href="/static/triforce_unsigned.png">
            <meta charset="UTF-8">
            <title>Signal API | Live Log</title>
            <style>
                body {
                    margin: 0;
                    background: #111;
                    color: #ddd;
                    font-family: Consolas, monospace;
                }

                .toolbar {
                    position: sticky;
                    top: 0;
                    background: #1b1b1b;
                    border-bottom: 1px solid #333;
                    padding: 10px;
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }

                button {
                    background: #2a2a2a;
                    color: #ddd;
                    border: 1px solid #444;
                    padding: 6px 10px;
                    cursor: pointer;
                }

                button:hover {
                    background: #333;
                }

                #log {
                    white-space: pre-wrap;
                    padding: 12px;
                    margin: 0;
                    line-height: 1.35;
                }

                .error { color: #ff6b6b; font-weight: bold; }
                .warn  { color: #ffd166; }
                .info  { color: #72c7ff; }
                .debug { color: #999; }
                .time  { color: #777; }
            </style>
        </head>
        <body>
            <div class="toolbar">
                <button onclick="togglePause()" id="pauseBtn">Pause</button>
                <button onclick="scrollToBottom()">Go down</button>
                <span id="status">loading...</span>
            </div>

            <pre id="log"></pre>

            <script>
                const logElement = document.getElementById("log");
                const statusElement = document.getElementById("status");
                const pauseBtn = document.getElementById("pauseBtn");

                let paused = false;
                let lastText = "";

                function escapeHtml(text) {
                    return text
                        .replaceAll("&", "&amp;")
                        .replaceAll("<", "&lt;")
                        .replaceAll(">", "&gt;");
                }

                function highlightLog(text) {
                    let html = escapeHtml(text);

                    html = html.replace(
                        /(\\d{2}\\.\\d{2}\\.\\d{4} \\d{2}:\\d{2}:\\d{2})/g,
                        '<span class="time">$1</span>'
                    );

                    html = html.replace(/\\[ERROR\\]/g, '<span class="error">[ERROR]</span>');
                    html = html.replace(/\\[WARNING\\]/g, '<span class="warn">[WARNING]</span>');
                    html = html.replace(/\\[WARN\\]/g, '<span class="warn">[WARN]</span>');
                    html = html.replace(/\\[INFO\\]/g, '<span class="info">[INFO]</span>');
                    html = html.replace(/\\[DEBUG\\]/g, '<span class="debug">[DEBUG]</span>');

                    return html;
                }

                function isNearBottom() {
                    return window.innerHeight + window.scrollY >= document.body.offsetHeight - 100;
                }

                function scrollToBottom() {
                    window.scrollTo(0, document.body.scrollHeight);
                }

                function togglePause() {
                    paused = !paused;
                    pauseBtn.textContent = paused ? "Resume" : "Pause";
                    statusElement.textContent = paused ? "paused" : "live";
                }

                async function refreshLog() {
                    if (paused) {
                        return;
                    }

                    try {
                        const shouldStick = isNearBottom();

                        const response = await fetch("%s", { cache: "no-store" });
                        const text = await response.text();

                        if (text !== lastText) {
                            lastText = text;
                            logElement.innerHTML = highlightLog(text);

                            if (shouldStick) {
                                scrollToBottom();
                            }
                        }

                        statusElement.textContent = "live";
                    } catch (e) {
                        statusElement.textContent = "connection error";
                    }
                }

                refreshLog();
                setInterval(refreshLog, 1000);
            </script>
        </body>
        </html>
        """ % f"{ApiUrl.API}{ApiUrl.RAW_LOG}"
