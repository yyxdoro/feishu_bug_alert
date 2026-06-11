import json
import configparser
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

cfg = configparser.ConfigParser()
cfg.read(Path(__file__).with_name("config.ini"), encoding="utf-8")
APP_ID = cfg["FEISHU"]["app_id"]
APP_SECRET = cfg["FEISHU"]["app_secret"]
BASE_APP_ID = cfg["FEISHU"]["base_app_id"]
TABLE_ID = cfg["FEISHU"]["table_id"]
CLOSED_STATUS = [s.strip() for s in cfg["FEISHU"]["closed_status"].split(",") if s.strip()]
REMIND_TITLE = cfg["FEISHU"]["remind_title"]
STATUS_FIELD_NAME = cfg["FEISHU"].get("status_field_name", "进度")
TITLE_FIELD_NAME = cfg["FEISHU"].get("title_field_name", "Bug标题")
ASSIGNEE_FIELD_NAME = cfg["FEISHU"].get("assignee_field_name", "指派人")
DEBUG_ENABLED = cfg["FEISHU"].getboolean("debug_enabled", fallback=False)
DEBUG_FILTER_FIELD_NAME = cfg["FEISHU"].get(
    "debug_filter_field_name",
    cfg["FEISHU"].get("creator_field_name", "创建人")
)
DEBUG_FILTER_USER_NAME = cfg["FEISHU"].get(
    "debug_filter_user_name",
    cfg["FEISHU"].get("creator_name", "杨玉霞")
)
VIEW_ID = cfg["FEISHU"].get("view_id", "").strip()
VIEW_NAME = cfg["FEISHU"].get("view_name", "Tripo 需求一览表").strip()
SUBMIT_LINK = cfg["FEISHU"].get("submit_link", "").strip()
DEBUG_TARGET_ASSIGNEE_NAMES = [
    s.strip() for s in cfg["FEISHU"].get("debug_target_assignee_names", "").split(",") if s.strip()
]
PRIORITY_FIELD_NAME = cfg["FEISHU"].get("priority_field_name", "优先级")
DETAIL_ROW_LIMIT = cfg["FEISHU"].getint("detail_row_limit", fallback=10)
SEND_ENABLED = cfg["FEISHU"].getboolean("send_enabled", fallback=False)
CREATE_VIEWS_ENABLED = cfg["FEISHU"].getboolean("create_views_enabled", fallback=True)
REQUIRE_VALID_PERSON_VIEW = cfg["FEISHU"].getboolean("require_valid_person_view", fallback=True)
FALLBACK_TO_BASE_LINK = cfg["FEISHU"].getboolean("fallback_to_base_link", fallback=False)


def _http_json(method, url, headers=None, params=None, body=None):
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    _, text = _http_json(
        "POST",
        url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    resp = json.loads(text)
    if resp.get("code", 0) != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {resp.get('code')} {resp.get('msg')}")
    return resp["tenant_access_token"]


def _feishu_request(method, url, token, params=None, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    status_code, text = _http_json(method, url, headers=headers, params=params, body=body)
    try:
        return json.loads(text)
    except Exception:
        return {"code": -1, "msg": f"Non-JSON response: {status_code}", "data": {"raw": text}}


def _require_success(res, action):
    if res.get("code") not in (0, None):
        raise RuntimeError(f"{action}失败: {res.get('code')} {res.get('msg')}")


def _get_status_value(fields):
    value = fields.get(STATUS_FIELD_NAME)
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    return str(value or "").strip()


def _is_closed_status(fields):
    status_value = _get_status_value(fields)
    if isinstance(status_value, list):
        return any(status in CLOSED_STATUS for status in status_value)
    return status_value in CLOSED_STATUS


def _filter_open_records(records):
    return [r for r in records if not _is_closed_status(r.get("fields", {}))]


def query_bitable_data(token):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/records/search"
    return _search_bitable_records(token, url, body={})


def _search_bitable_records(token, url, body=None):
    all_records = []
    page_token = ""
    seen_page_tokens = set()
    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        res = _feishu_request("POST", url, token, params=params, body=body or {})
        _require_success(res, "查询多维表格记录")
        data = res.get("data", {})
        all_records.extend(data.get("items", []))
        next_page_token = data.get("page_token", "")
        if not next_page_token or next_page_token in seen_page_tokens:
            break
        seen_page_tokens.add(next_page_token)
        page_token = next_page_token
    return _filter_open_records(all_records)


def query_assignee_records(token, open_id):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/records/search"
    body = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": ASSIGNEE_FIELD_NAME, "operator": "contains", "value": [open_id]},
            ],
        }
    }
    return _filter_records_by_assignee_open_id(_search_bitable_records(token, url, body=body), open_id)


def _as_person_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _extract_person_open_id(person):
    if not isinstance(person, dict):
        return ""
    return str(person.get("id") or "").strip()


def _extract_person_name(person):
    if not isinstance(person, dict):
        return ""
    return str(person.get("name") or "").strip()


def _filter_records_by_assignee_open_id(records, open_id):
    return [
        record for record in records
        if any(
            _extract_person_open_id(person) == open_id
            for person in _as_person_list(record.get("fields", {}).get(ASSIGNEE_FIELD_NAME))
        )
    ]


def _is_person_name_match(fields, field_name, person_name):
    value = fields.get(field_name)
    if isinstance(value, str):
        return value.strip() == person_name
    persons = _as_person_list(value)
    return any(_extract_person_name(p) == person_name for p in persons)


def filter_records_by_person_name(records, field_name, person_name):
    return [
        r for r in records
        if _is_person_name_match(r.get("fields", {}), field_name, person_name)
    ]


def get_filter_link(view_id=""):
    if view_id:
        return f"https://feishu.cn/base/{BASE_APP_ID}?table={TABLE_ID}&view={view_id}"
    return f"https://feishu.cn/base/{BASE_APP_ID}?table={TABLE_ID}"


def get_record_link(record_id):
    return f"https://feishu.cn/base/{BASE_APP_ID}?table={TABLE_ID}&record={record_id}"


def list_views(token):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/views"
    res = _feishu_request("GET", url, token)
    if res.get("code") not in (0, None):
        print(f"获取视图列表失败: {res.get('code')} {res.get('msg')}")
        return []
    items = res.get("data", {}).get("items", [])
    if isinstance(items, list):
        return items
    return []


def list_fields(token):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/fields"
    res = _feishu_request("GET", url, token)
    _require_success(res, "获取字段列表")
    return res.get("data", {}).get("items", []) or []


def _field_by_name(fields, field_name):
    for field in fields:
        if field.get("field_name") == field_name:
            return field
    raise RuntimeError(f"找不到字段: {field_name}")


def _single_select_option_id(field, option_name):
    for option in (field.get("property") or {}).get("options", []):
        if option.get("name") == option_name:
            return option.get("id")
    raise RuntimeError(f"找不到单选项: {field.get('field_name')}={option_name}")


def create_view(token, view_name):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/views"
    body = {"view_name": view_name, "view_type": "grid"}
    return _feishu_request("POST", url, token, body=body)


def _target_view_name(person_name):
    return f"{person_name}-未闭环BUG"


def _view_record_names(token, view_id):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/records/search"
    records = _search_bitable_records(token, url, body={"view_id": view_id})
    names = set()
    for record in records:
        for person in _as_person_list(record.get("fields", {}).get(ASSIGNEE_FIELD_NAME)):
            name = _extract_person_name(person)
            if name:
                names.add(name)
    return names


def _is_valid_person_view(token, view_id, open_id):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/records/search"
    records = _search_bitable_records(token, url, body={"view_id": view_id})
    if not records:
        return False
    for record in records:
        assignees = _as_person_list(record.get("fields", {}).get(ASSIGNEE_FIELD_NAME))
        if not any(_extract_person_open_id(person) == open_id for person in assignees):
            return False
    return True


def _person_filter_info(fields, open_id):
    assignee_field = _field_by_name(fields, ASSIGNEE_FIELD_NAME)
    status_field = _field_by_name(fields, STATUS_FIELD_NAME)
    conditions = [
        {
            "field_id": assignee_field["field_id"],
            "operator": "is",
            "value": json.dumps([open_id], ensure_ascii=False),
        },
    ]
    for status in CLOSED_STATUS:
        conditions.append({
            "field_id": status_field["field_id"],
            "operator": "isNot",
            "value": json.dumps([_single_select_option_id(status_field, status)], ensure_ascii=False),
        })
    return {
        "conditions": conditions,
        "conjunction": "and",
    }


def update_view_filter(token, view_id, view_name, filter_info):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_ID}/tables/{TABLE_ID}/views/{view_id}"
    body = {
        "view_name": view_name,
        "property": {
            "filter_info": filter_info,
            "hidden_fields": None,
        },
    }
    res = _feishu_request("PATCH", url, token, body=body)
    _require_success(res, f"更新视图筛选 {view_name}")
    return res


def ensure_person_view(token, fields, person_name, open_id):
    if VIEW_ID and _is_valid_person_view(token, VIEW_ID, open_id):
        return VIEW_ID
    if not CREATE_VIEWS_ENABLED:
        return ""

    target_view_name = _target_view_name(person_name)
    views = list_views(token)
    view_id = ""
    for v in views:
        if str(v.get("view_name") or "").strip() == target_view_name:
            view_id = str(v.get("view_id") or "").strip()
            break

    if not view_id:
        created = create_view(token, target_view_name)
        _require_success(created, f"创建视图 {target_view_name}")
        view_id = str(created.get("data", {}).get("view", {}).get("view_id") or "").strip()
        if not view_id:
            raise RuntimeError(f"创建视图 {target_view_name} 成功但没有返回 view_id")

    update_view_filter(token, view_id, target_view_name, _person_filter_info(fields, open_id))
    return view_id


def get_person_filter_link(token, fields, person_name, open_id):
    view_id = ensure_person_view(token, fields, person_name, open_id)
    if not view_id:
        raise RuntimeError(f"{person_name} 未生成个人筛选视图，停止发送，避免发送整表链接")
    if REQUIRE_VALID_PERSON_VIEW and not _is_valid_person_view(token, view_id, open_id):
        raise RuntimeError(f"{person_name} 视图未通过个人筛选校验，停止发送: {view_id}")
    return get_filter_link(view_id)


def _rich_text_to_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "".join(str(item.get("text") or item.get("link") or "") for item in value if isinstance(item, dict)).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("link") or "").strip()
    return str(value or "").strip()


def _get_bug_title(fields):
    title = _rich_text_to_text(fields.get(TITLE_FIELD_NAME))
    if title:
        return title
    description = _rich_text_to_text(fields.get("bug 描述"))
    bug_id = _rich_text_to_text(fields.get("bugID"))
    if description and bug_id:
        return f"BUG-{bug_id} {description}"
    return description or (f"BUG-{bug_id}" if bug_id else "无标题")


def group_by_assignee(records):
    user_map = defaultdict(lambda: {"name": "", "bug_lines": []})
    for item in records:
        fields = item.get("fields", {})
        bug_name = _get_bug_title(fields)
        assignees = _as_person_list(fields.get(ASSIGNEE_FIELD_NAME))
        if not assignees:
            continue
        content_line = f"· {bug_name}"
        for user in assignees:
            open_id = _extract_person_open_id(user)
            if not open_id:
                continue
            user_map[open_id]["name"] = _extract_person_name(user) or open_id
            user_map[open_id]["bug_lines"].append(content_line)
    return user_map


def send_feish_msg(open_id, title, content, token):
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    body = {
        "receive_id": open_id,
        "msg_type": "post",
        "content": json.dumps({
            "zh_cn": {
                "title": title,
                "content": content,
            }
        }, ensure_ascii=False)
    }
    res = _feishu_request("POST", url, token, body=body)
    if res.get("code") != 0:
        print(f"发送消息失败 open_id={open_id}: {res.get('code')} {res.get('msg')}")
    return res


def _filter_group_data(group_data):
    if not DEBUG_TARGET_ASSIGNEE_NAMES:
        return group_data
    return {
        open_id: data
        for open_id, data in group_data.items()
        if data.get("name") in DEBUG_TARGET_ASSIGNEE_NAMES
    }


def _get_field_text(fields, field_name):
    value = fields.get(field_name)
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            names = [_extract_person_name(item) or _rich_text_to_text(item) for item in value]
            return "、".join(name for name in names if name)
        return "、".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return _extract_person_name(value) or _rich_text_to_text(value)
    return str(value or "").strip()


def _priority_value(fields):
    priority = _get_field_text(fields, PRIORITY_FIELD_NAME)
    return priority or "未填写"


def _summarize_records(records):
    priority_counts = defaultdict(int)
    detail_lines = []
    for record in records:
        fields = record.get("fields", {})
        priority = _priority_value(fields)
        priority_counts[priority] += 1
        if len(detail_lines) < DETAIL_ROW_LIMIT:
            status = _get_status_value(fields)
            if isinstance(status, list):
                status = "、".join(status)
            detail_lines.append(
                f"{len(detail_lines) + 1}. [{priority}] {status or '无状态'} - {_get_bug_title(fields)}"
            )

    priority_order = ["P0", "P1", "P2", "P3", "P4", "未填写"]
    summary_parts = []
    for priority in priority_order:
        count = priority_counts.pop(priority, 0)
        if count:
            summary_parts.append(f"{priority}: {count}")
    summary_parts.extend(f"{priority}: {count}" for priority, count in sorted(priority_counts.items()))
    return summary_parts, detail_lines


def _build_conclusion(total_count, priority_summary):
    urgent_parts = []
    for item in priority_summary:
        name, _, count = item.partition(": ")
        if name in {"P0", "P1"} and count and count != "0":
            urgent_parts.append(item)
    if urgent_parts:
        return f"结论：当前存在高优先级未闭环 Bug（{'，'.join(urgent_parts)}），请优先处理。"
    if total_count:
        return "结论：当前无 P0/P1 未闭环 Bug，请按计划处理剩余问题。"
    return "结论：当前没有未闭环 Bug。"


def _build_message_content(assignee_name, filter_link, records):
    total_count = len(records)
    priority_summary, detail_lines = _summarize_records(records)
    content = [
        [{"tag": "text", "text": f"指派人：{assignee_name}"}],
        [{"tag": "text", "text": f"名下未闭环 Bug 数：{total_count}"}],
        [{"tag": "text", "text": f"优先级统计：{('，'.join(priority_summary) if priority_summary else '无')}"}],
        [{"tag": "text", "text": _build_conclusion(total_count, priority_summary)}],
    ]
    if detail_lines:
        content.append([{"tag": "text", "text": "筛选后表格明细：\n" + "\n".join(detail_lines)}])
        if total_count > len(detail_lines):
            content.append([{"tag": "text", "text": f"还有 {total_count - len(detail_lines)} 条未展示，请点击筛选链接查看全部。"}])
    if filter_link:
        content.append([
            {"tag": "text", "text": "名下筛选Bug链接："},
            {"tag": "a", "text": VIEW_NAME, "href": filter_link},
        ])
    content.append([
        {"tag": "text", "text": "提单链接："},
        {"tag": "a", "text": "提交问题表单", "href": SUBMIT_LINK},
    ])
    return content


def _message_content_to_text(content):
    lines = []
    for block in content:
        line_parts = []
        for item in block:
            text = item.get("text", "")
            href = item.get("href", "")
            line_parts.append(f"{text} {href}".strip() if href else text)
        lines.append("".join(line_parts))
    return "\n".join(lines)


def _find_target_people(records):
    targets = {}
    target_names = set(DEBUG_TARGET_ASSIGNEE_NAMES)
    person_fields = [ASSIGNEE_FIELD_NAME, DEBUG_FILTER_FIELD_NAME]
    for record in records:
        fields = record.get("fields", {})
        for field_name in person_fields:
            for person in _as_person_list(fields.get(field_name)):
                name = _extract_person_name(person)
                open_id = _extract_person_open_id(person)
                if name in target_names and open_id:
                    targets[open_id] = {"name": name, "bug_lines": []}
    return targets


def main(send_enabled=SEND_ENABLED):
    token = get_tenant_token()
    records = query_bitable_data(token)
    print(f"未闭环 Bug 数量: {len(records)}")

    if DEBUG_ENABLED:
        source_records = filter_records_by_person_name(records, DEBUG_FILTER_FIELD_NAME, DEBUG_FILTER_USER_NAME)
        print(f"调试筛选 {DEBUG_FILTER_FIELD_NAME}={DEBUG_FILTER_USER_NAME} 后数量: {len(source_records)}")
    else:
        source_records = records

    group_data = group_by_assignee(source_records)
    if DEBUG_TARGET_ASSIGNEE_NAMES:
        target_people = _find_target_people(records)
        group_data.update(target_people)
    group_data = _filter_group_data(group_data)
    if not group_data:
        print("没有找到可提醒的指派人 Bug")
        return

    fields = list_fields(token)

    for open_id, assignee_data in group_data.items():
        assignee_name = assignee_data["name"]
        debug_records = query_assignee_records(token, open_id)
        print(f"{assignee_name} 未闭环记录数: {len(debug_records)}")
        try:
            filter_link = get_person_filter_link(token, fields, assignee_name, open_id)
        except Exception as exc:
            print(f"{assignee_name} 跳过发送: {exc}")
            continue
        print(f"{assignee_name} 视图链接: {filter_link}")
        content = _build_message_content(assignee_name, filter_link, debug_records)
        if not send_enabled:
            print(f"未发送消息，send_enabled=false: {assignee_name}")
            print(_message_content_to_text(content))
            continue
        res = send_feish_msg(open_id, REMIND_TITLE, content, token)
        print({"name": assignee_name, "open_id": open_id, "code": res.get("code"), "msg": res.get("msg")})


def run_once():
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"手动触发飞书 Bug 提醒开始: {now}", flush=True)
    main(send_enabled=True)
    done_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"手动触发飞书 Bug 提醒完成: {done_at}", flush=True)


if __name__ == "__main__":
    run_once()
