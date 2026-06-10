import json
from datetime import datetime
from zoneinfo import ZoneInfo

from feishu_bug_alert import (
    ASSIGNEE_FIELD_NAME,
    DEBUG_FILTER_FIELD_NAME,
    REMIND_TITLE,
    _as_person_list,
    _build_message_content,
    _extract_person_name,
    _extract_person_open_id,
    _feishu_request,
    _message_content_to_text,
    ensure_person_view,
    get_filter_link,
    get_tenant_token,
    group_by_assignee,
    list_fields,
    query_assignee_records,
    query_bitable_data,
)


TARGET_EMAIL = "yangyuxia@vastai3d.com"
TARGET_NAME = "杨玉霞"


def _find_target_open_id(records):
    for record in records:
        fields = record.get("fields", {})
        for field_name in (ASSIGNEE_FIELD_NAME, DEBUG_FILTER_FIELD_NAME):
            for person in _as_person_list(fields.get(field_name)):
                if _extract_person_name(person) == TARGET_NAME:
                    open_id = _extract_person_open_id(person)
                    if open_id:
                        return open_id
    return ""


def _send_debug_email(token, content):
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=email"
    body = {
        "receive_id": TARGET_EMAIL,
        "msg_type": "post",
        "content": json.dumps(
            {
                "zh_cn": {
                    "title": f"{REMIND_TITLE} 调试消息",
                    "content": content,
                }
            },
            ensure_ascii=False,
        ),
    }
    return _feishu_request("POST", url, token, body=body)


def main():
    token = get_tenant_token()
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    records = query_bitable_data(token)
    print(f"未闭环 Bug 数量: {len(records)}")

    group_data = group_by_assignee(records)
    target_open_id = ""
    for open_id, data in group_data.items():
        if data.get("name") == TARGET_NAME:
            target_open_id = open_id
            break
    if not target_open_id:
        target_open_id = _find_target_open_id(records)
    if not target_open_id:
        raise RuntimeError(f"没有在多维表人员字段中找到 {TARGET_NAME} 的 open_id")

    fields = list_fields(token)
    target_records = query_assignee_records(token, target_open_id)
    print(f"{TARGET_NAME} 未闭环记录数: {len(target_records)}")

    view_id = ensure_person_view(token, fields, TARGET_NAME, target_open_id)
    filter_link = get_filter_link(view_id) if view_id else get_filter_link()
    print(f"{TARGET_NAME} 视图链接: {filter_link}")

    content = _build_message_content(TARGET_NAME, filter_link, target_records)
    content.append([{"tag": "text", "text": f"调试发送对象：{TARGET_EMAIL}"}])
    content.append([{"tag": "text", "text": f"调试发送时间：{now}"}])
    print(_message_content_to_text(content))

    res = _send_debug_email(token, content)
    print({"target_name": TARGET_NAME, "target_email": TARGET_EMAIL, "code": res.get("code"), "msg": res.get("msg")})


if __name__ == "__main__":
    main()
