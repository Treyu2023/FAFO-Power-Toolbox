            }
        });

        // ΓöÇΓöÇ Server Watchdog UI ΓöÇΓöÇ
        function applyWatchdogStatus(wd) {
            const dot = document.getElementById('dotWatchdog');
            const txt = document.getElementById('txtWatchdog');
            const hint = document.getElementById('watchdogHint');
            if (!wd) {
                setDot(dot, false);
                if (txt) {
                    txt.innerHTML = 'Monitor status unknown ΓÇö click <strong>Start monitor</strong> or open bat files if S1 is offline';
                }
                if (hint) hint.textContent = 'Uses protocol launch when S1 is offline.';
                return;
            }
            const running = !!wd.running;
            const attention = !!wd.attentionRequired;
            setDot(dot, running && !attention);
            if (dot && attention) {
                dot.className = 'server-dot wait';
            }
            const rep = wd.report || {};
            const s = rep.servers || {};
            const s1 = s.s1_up ? 'S1 up' : 'S1 down';
            const s2 = s.s2_up ? 'S2 up' : 'S2 down';
            if (txt) {
                txt.innerHTML = running
                    ? `<strong style="color:${attention ? '#ffc800' : 'var(--ok, #00ff88)'}">${attention ? 'ATTENTION' : 'Monitoring'}</strong> ┬╖ ${s1} ┬╖ ${s2}`
                    : `<strong style="color:#ff8a9a">Monitor not running</strong> ┬╖ click Γû╢ Start monitor`;
            }
            if (hint) {
                if (attention) {
                    hint.textContent = rep.attentionReason || 'See status page / ATTENTION-SERVERS.txt';
                    hint.style.color = '#ffc800';
                } else {
                    hint.textContent = running ? 'Auto-heal on ┬╖ status page refreshes every 30s' : '';
                    hint.style.color = '';
                }
            }
        }

        async function refreshWatchdog() {
            try {
                const wd = AIToolboxAPI.getWatchdogStatus
                    ? await AIToolboxAPI.getWatchdogStatus()
                    : null;
                applyWatchdogStatus(wd);
                return wd;
            } catch {
                applyWatchdogStatus(null);
                return null;
            }
        }

        async function runWatchdogAction(kind) {
            const hint = document.getElementById('watchdogHint');
            const labels = {
                start: 'Starting monitorΓÇª',
                status: 'Opening statusΓÇª',
                install: 'Installing auto-startΓÇª',
                folder: 'Opening bat files folderΓÇª',
            };
            if (hint) {
                hint.style.color = '';
                hint.textContent = labels[kind] || 'WorkingΓÇª';
            }
            try {
                let r = null;
                if (kind === 'start' && AIToolboxAPI.startWatchdog) {
                    r = await AIToolboxAPI.startWatchdog();
                } else if (kind === 'status' && AIToolboxAPI.openWatchdogStatus) {
                    r = await AIToolboxAPI.openWatchdogStatus();
                } else if (kind === 'install' && AIToolboxAPI.installWatchdog) {
                    r = await AIToolboxAPI.installWatchdog();
                } else if (kind === 'folder' && AIToolboxAPI.openWatchdogBatsFolder) {
                    r = await AIToolboxAPI.openWatchdogBatsFolder();
                } else {
                    // Hard fallback: map to bat names via protocol
                    const map = {
                        start: 'Start-Server-Watchdog.bat',
                        status: 'Open-Server-Watchdog-Status.bat',
                        install: 'Install-Server-Watchdog.bat',
                    };
                    if (kind === 'folder') {
                        AIToolboxAPI.tryProtocolLaunch?.('watchdog-folder')
                            || AIToolboxAPI.openToolboxFolder?.();
                    } else if (map[kind]) {
                        AIToolboxAPI.launchToolboxFile?.(map[kind]);
                    }
                    r = { ok: true, via: 'fallback' };
                }
                await new Promise((res) => setTimeout(res, kind === 'start' || kind === 'install' ? 1200 : 400));
                await refreshWatchdog();
                const ok = !r || r.ok !== false;
                AIToolboxUI.toast(
                    ok
                        ? (kind === 'start' ? 'Watchdog started'
                            : kind === 'install' ? 'Watchdog auto-start installed'
                            : kind === 'status' ? 'Status page opened'
                            : 'Opened bat folder')
                        : (r.error || 'Action may have failed ΓÇö try Bat files'),
                    ok ? 'ok' : 'warn'
                );
                if (hint && ok) {
                    hint.textContent = kind === 'folder'
                        ? 'Explorer should show Start-Server-Watchdog.bat selected'
                        : (labels[kind] || 'Done').replace('ΓÇª', ' Γ£ô');
                }
            } catch (e) {
                if (hint) hint.textContent = String(e.message || e);
                AIToolboxUI.toast(String(e.message || e) + ' ΓÇö try ≡ƒôé Bat files', 'warn');
                // Last resort open folder
                try {
                    AIToolboxAPI.tryProtocolLaunch?.('watchdog-folder')
                        || AIToolboxAPI.openToolboxFolder?.();
                } catch { /* ignore */ }
            }
        }

        document.getElementById('btnWatchdogStart')?.addEventListener('click', () => runWatchdogAction('start'));
        document.getElementById('btnWatchdogStatus')?.addEventListener('click', () => runWatchdogAction('status'));
        document.getElementById('btnWatchdogStatusTop')?.addEventListener('click', () => runWatchdogAction('status'));
        document.getElementById('btnWatchdogInstall')?.addEventListener('click', () => runWatchdogAction('install'));
        document.getElementById('btnWatchdogFolder')?.addEventListener('click', () => runWatchdogAction('folder'));
        document.getElementById('btnWatchdogRefresh')?.addEventListener('click', async () => {
            document.getElementById('watchdogHint').textContent = 'RefreshingΓÇª';
            await refreshWatchdog();
        });