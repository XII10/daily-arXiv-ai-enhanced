import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

# 自动读取上一步生成的Markdown文件
with open("latest_md_file.txt", "r", encoding="utf-8") as f:
    md_file = f.read().strip()

# 读取Markdown内容
with open(md_file, "r", encoding="utf-8") as f:
    md_content = f.read()

# 从GitHub Secrets读取你之前配置的邮箱信息
sender_email = os.environ.get("SENDER_EMAIL", "")
sender_auth_code = os.environ.get("EMAIL_AUTH_CODE", "")
receiver_email = os.environ.get("RECEIVER_EMAIL", "")
smtp_server = os.environ.get("SMTP_SERVER", "smtp.qq.com")
smtp_port = int(os.environ.get("SMTP_PORT", 465))

# 构造邮件
msg = MIMEText(md_content, "markdown", "utf-8")
today = datetime.now().strftime("%Y年%m月%d日")
msg["From"] = Header(f"文献自动推送助手 <{sender_email}>", "utf-8")
msg["To"] = Header(receiver_email, "utf-8")
msg["Subject"] = Header(f"{today} 光催化/接触电催化固氮最新文献汇总", "utf-8")

# 发送邮件
try:
    smtp = smtplib.SMTP_SSL(smtp_server, smtp_port)
    smtp.login(sender_email, sender_auth_code)
    smtp.sendmail(sender_email, receiver_email, msg.as_string())
    smtp.quit()
    print("文献汇总邮件已成功发送到你的邮箱！")
except Exception as e:
    print(f"邮件发送失败：{str(e)}")
    raise e
