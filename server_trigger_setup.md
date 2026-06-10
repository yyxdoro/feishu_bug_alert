# 服务器部署 scheduler 设置

推荐在 Linux 服务器上使用 `systemd` 常驻运行 `feishu_bug_alert.py`，由脚本内 APScheduler 每天 14:00 触发提醒。

## 1. 项目路径

当前服务器项目部署在：

```bash
/home/ec2-user/yuha/feishu_bug_alert
```

脚本入口：

```bash
/home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py
```

Python 虚拟环境：

```bash
/home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3
```

日志目录：

```bash
/home/ec2-user/yuha/feishu_bug_alert/logs
```

## 2. 创建日志目录

```bash
mkdir -p /home/ec2-user/yuha/feishu_bug_alert/logs
```

## 3. 安装依赖

```bash
cd /home/ec2-user/yuha/feishu_bug_alert
/home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3 -m pip install -r requirements.txt
```

## 4. 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/feishu-bug-alert.service >/dev/null <<'EOF'
[Unit]
Description=Feishu bug alert scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ec2-user/yuha/feishu_bug_alert
ExecStart=/home/ec2-user/yuha/feishu_bug_alert/.venv/bin/python3 /home/ec2-user/yuha/feishu_bug_alert/feishu_bug_alert.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ec2-user/yuha/feishu_bug_alert/logs/scheduler.log
StandardError=append:/home/ec2-user/yuha/feishu_bug_alert/logs/scheduler.err.log

[Install]
WantedBy=multi-user.target
EOF
```

## 5. 启动并设置开机自启

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now feishu-bug-alert.service
```

## 6. 查看运行状态

```bash
systemctl status feishu-bug-alert.service
```

确认日志包含：

```text
Feishu bug alert scheduler started: Asia/Shanghai, every day 14:00
```

## 7. 查看日志

```bash
tail -n 100 /home/ec2-user/yuha/feishu_bug_alert/logs/scheduler.log
tail -n 100 /home/ec2-user/yuha/feishu_bug_alert/logs/scheduler.err.log
```

## 8. 停用旧 crontab

```bash
crontab -l
```

如果仍有旧的 `feishu_bug_alert.py` 定时行，需要从 `crontab -e` 中删除，避免同一天重复发送。

## 9. 注意事项

- `feishu_bug_alert.py` 已指定 `Asia/Shanghai`，每天 14:00 触发。
- 用 `date` 检查服务器当前时间。
- 不要直接调用 `main()` 做线上调试；如需调试发送，请先把收件人限制为杨玉霞。
- 不要把 `app_secret` 提交到公开仓库；生产环境更推荐改成环境变量或服务器私有配置文件。
