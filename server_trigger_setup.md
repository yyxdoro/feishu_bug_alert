# 服务器部署触发器设置

推荐在 Linux 服务器上使用 `cron` 定时触发，不建议用当前 macOS 的 `launchd` 配置。

## 1. 项目路径假设

假设项目部署在：

```bash
/opt/feishu_bug_alert
```

脚本入口：

```bash
/opt/feishu_bug_alert/feishu_bug_alert.py
```

Python 虚拟环境：

```bash
/opt/feishu_bug_alert/.venv/bin/python
```

日志目录：

```bash
/opt/feishu_bug_alert/logs
```

## 2. 创建日志目录

```bash
mkdir -p /opt/feishu_bug_alert/logs
```

## 3. 编辑 crontab

```bash
crontab -e
```

添加下面这一行，表示每周一到周五 15:45 执行：

```cron
45 15 * * 1-5 cd /opt/feishu_bug_alert && /opt/feishu_bug_alert/.venv/bin/python /opt/feishu_bug_alert/feishu_bug_alert.py >> /opt/feishu_bug_alert/logs/feishu_bug_alert.out.log 2>> /opt/feishu_bug_alert/logs/feishu_bug_alert.err.log
```

## 4. 查看是否已写入

```bash
crontab -l
```

## 5. 手动测试一次

```bash
cd /opt/feishu_bug_alert && /opt/feishu_bug_alert/.venv/bin/python /opt/feishu_bug_alert/feishu_bug_alert.py
```

## 6. 查看日志

```bash
tail -n 100 /opt/feishu_bug_alert/logs/feishu_bug_alert.out.log
tail -n 100 /opt/feishu_bug_alert/logs/feishu_bug_alert.err.log
```

## 7. 注意事项

- 服务器时区必须正确，否则 15:45 可能不是北京时间。
- 用 `date` 检查服务器当前时间。
- 如果服务器是 UTC，而你想按北京时间 15:45 执行，cron 时间应改成 UTC 07:45：

```cron
45 7 * * 1-5 cd /opt/feishu_bug_alert && /opt/feishu_bug_alert/.venv/bin/python /opt/feishu_bug_alert/feishu_bug_alert.py >> /opt/feishu_bug_alert/logs/feishu_bug_alert.out.log 2>> /opt/feishu_bug_alert/logs/feishu_bug_alert.err.log
```

- 不要把 `app_secret` 提交到公开仓库；生产环境更推荐改成环境变量或服务器私有配置文件。
