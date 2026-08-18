using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Windows.Forms;

namespace CatiaWorkerTray
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new TrayContext());
        }
    }

    internal sealed class TrayContext : ApplicationContext
    {
        private readonly NotifyIcon trayIcon;
        private readonly Timer statusTimer;
        private readonly string repoRoot;
        private readonly string backendRoot;
        private readonly string logPath;
        private Process workerProcess;

        public TrayContext()
        {
            repoRoot = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", ".."));
            backendRoot = Path.Combine(repoRoot, "backend");
            logPath = Path.Combine(repoRoot, ".runtime", "catia-worker-tray.log");
            Directory.CreateDirectory(Path.GetDirectoryName(logPath));

            trayIcon = new NotifyIcon
            {
                Icon = SystemIcons.Application,
                Text = "CATIA Worker",
                Visible = true,
                ContextMenuStrip = BuildMenu()
            };
            trayIcon.DoubleClick += delegate { StartWorker(); };

            statusTimer = new Timer { Interval = 5000 };
            statusTimer.Tick += delegate { UpdateStatus(); };
            statusTimer.Start();

            StartWorker();
        }

        private ContextMenuStrip BuildMenu()
        {
            var menu = new ContextMenuStrip();
            menu.Items.Add("启动 Worker", null, delegate { StartWorker(); });
            menu.Items.Add("停止 Worker", null, delegate { StopWorker(); });
            menu.Items.Add("打开 Worker 地址", null, delegate { Process.Start("http://127.0.0.1:5182/health"); });
            menu.Items.Add("打开日志", null, delegate { OpenLog(); });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出", null, delegate { ExitApplication(); });
            return menu;
        }

        private void StartWorker()
        {
            if (IsPortHealthy())
            {
                SetHealthyText();
                return;
            }
            if (workerProcess != null && !workerProcess.HasExited)
            {
                return;
            }
            if (!Directory.Exists(backendRoot))
            {
                ShowBalloon("启动失败", "找不到 backend 目录：" + backendRoot, ToolTipIcon.Error);
                return;
            }

            var command = "call conda activate 3dcad"
                + " && cd /d \"" + backendRoot + "\""
                + " && python -m uvicorn app.catia_worker.server:app --host 127.0.0.1 --port 5182"
                + " >> \"" + logPath + "\" 2>&1";

            var startInfo = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/d /c \"" + command + "\"",
                WorkingDirectory = backendRoot,
                CreateNoWindow = true,
                UseShellExecute = false
            };
            workerProcess = Process.Start(startInfo);
            trayIcon.Text = "CATIA Worker：启动中";
            ShowBalloon("CATIA Worker", "正在后台启动 CATIA Worker。", ToolTipIcon.Info);
        }

        private void StopWorker()
        {
            if (workerProcess == null || workerProcess.HasExited)
            {
                trayIcon.Text = "CATIA Worker：未运行";
                return;
            }
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "taskkill.exe",
                    Arguments = "/PID " + workerProcess.Id + " /T /F",
                    CreateNoWindow = true,
                    UseShellExecute = false
                }).WaitForExit(5000);
            }
            catch
            {
                try { workerProcess.Kill(); } catch { }
            }
            trayIcon.Text = "CATIA Worker：已停止";
            ShowBalloon("CATIA Worker", "Worker 已停止。", ToolTipIcon.Info);
        }

        private void UpdateStatus()
        {
            if (IsPortHealthy())
            {
                SetHealthyText();
                return;
            }
            if (workerProcess != null && workerProcess.HasExited)
            {
                trayIcon.Text = "CATIA Worker：已退出";
                return;
            }
            trayIcon.Text = "CATIA Worker：启动中/不可达";
        }

        private bool IsPortHealthy()
        {
            try
            {
                var request = WebRequest.Create("http://127.0.0.1:5182/health");
                request.Timeout = 1000;
                using (var response = (HttpWebResponse)request.GetResponse())
                {
                    return response.StatusCode == HttpStatusCode.OK;
                }
            }
            catch
            {
                return false;
            }
        }

        private void SetHealthyText()
        {
            trayIcon.Text = "CATIA Worker：运行中 127.0.0.1:5182";
        }

        private void OpenLog()
        {
            if (!File.Exists(logPath))
            {
                File.WriteAllText(logPath, "", System.Text.Encoding.UTF8);
            }
            Process.Start("notepad.exe", "\"" + logPath + "\"");
        }

        private void ShowBalloon(string title, string message, ToolTipIcon icon)
        {
            trayIcon.BalloonTipTitle = title;
            trayIcon.BalloonTipText = message;
            trayIcon.BalloonTipIcon = icon;
            trayIcon.ShowBalloonTip(2500);
        }

        private void ExitApplication()
        {
            StopWorker();
            statusTimer.Stop();
            trayIcon.Visible = false;
            trayIcon.Dispose();
            Application.Exit();
        }
    }
}
