import json
import re
import requests
import urllib.parse
from io import BytesIO
from des import strEnc


def _solve_captcha(session, base_url, timeout):
    """获取验证码图片并识别"""
    captcha_resp = session.get(f"{base_url}/am/validate.code", timeout=timeout)
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        code = ocr.classification(captcha_resp.content)
        return code.strip()
    except ImportError:
        with open("captcha.png", "wb") as f:
            f.write(captcha_resp.content)
        return input(f"验证码图片已保存为 captcha.png，请输入验证码: ").strip()
    except Exception:
        return ""


def get_token(username: str, password: str, timeout=10):
    def transform(ticket):
        ticket = urllib.parse.unquote(ticket).split("-")
        str1 = ""
        str2 = ""
        for i in ticket[1]:
            str1 += str((int(i) + 5) % 10)
        for i in ticket[2]:
            if "0" <= i <= "9":
                str2 += str((int(i) + 5) % 10)
            elif 'A' <= i <= 'Z':
                if ord(i) + 10 > ord('Z'):
                    str2 += chr(ord(i) + 10 - 26)
                else:
                    str2 += chr(ord(i) + 10)
            else:
                if ord(i) + 15 > ord('z'):
                    str2 += chr(ord(i) + 15 - 26)
                else:
                    str2 += chr(ord(i) + 15)
        return str1, str2

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    session.trust_env = False
    base_url = "https://idm.swu.edu.cn"

    # Step 1: of.swu.edu.cn → 获取 state（不跟随重定向）
    response = session.get(
        "https://of.swu.edu.cn/cas/oauth/login/SWU_CAS2_FEDERAL?service="
        "https%3A%2F%2Fof.swu.edu.cn%2Fgateway%2Ffighter-middle%2Fapi%2Fintegrate%2Fuaap"
        "%2Fcas%2Fresolve-cas-return%3Fnext%3Dhttps%253A%252F%252Fof.swu.edu.cn%252F%2523"
        "%252FcasLogin%253Ffrom%253D%25252FappCenter",
        allow_redirects=False, timeout=timeout
    )
    state = urllib.parse.unquote(urllib.parse.unquote(response.headers['Location'])).split("state=")[1][0:32]

    # Step 2: 跟随到 uaaap，提取 service 参数
    response = session.get(response.headers['Location'], allow_redirects=False, timeout=timeout)
    response = session.get(response.headers['Location'], allow_redirects=True, timeout=timeout)
    service = urllib.parse.parse_qs(urllib.parse.urlparse(response.url).query)['service'][0]

    # Step 3: 重新请求 uaaap 带 federalEnable=true → 302 到 idm
    response = session.get(
        f"https://uaaap.swu.edu.cn/cas/login?service={urllib.parse.quote(service)}&federalEnable=true",
        allow_redirects=False, timeout=timeout
    )
    response = session.get(response.headers['Location'], allow_redirects=True, timeout=timeout)

    # Step 4: 从 idm 页面提取关键参数
    goto = re.search(r'name="goto"[^>]*value="([^"]+)"', response.text).group(1)
    sunqp = re.search(r'name="SunQueryParamsString"[^>]*value="([^"]+)"', response.text).group(1)
    random_key = re.search(r'id="random"[^>]*value="([^"]+)"', response.text).group(1)

    # Step 5: 获取验证码
    code = _solve_captcha(session, base_url, timeout)

    # Step 6: 用页面动态 random 密钥加密
    enc_user = strEnc(username, random_key, '', '')
    enc_pass = strEnc(password, random_key, '', '')

    data = {
        "IDToken1": enc_user,
        "IDToken2": enc_pass,
        "IDToken3": "",
        "goto": goto,
        "gotoOnFail": "",
        "SunQueryParamsString": sunqp,
        "encoded": "true",
        "validateCode": code,
        "gx_charset": "UTF-8"
    }

    # Step 7: POST 登录 idm
    response = session.post(f"{base_url}/am/UI/Login", data=data, allow_redirects=False, timeout=timeout)
    if response.status_code != 302:
        raise Exception("登录失败")

    # Step 8: 跟随重定向，获取 uaaap 的 ST
    url = response.headers['Location']
    sticket = None
    for _ in range(5):
        r = session.get(url, allow_redirects=False, timeout=timeout)
        loc = r.headers.get('Location', '')
        if 'ticket=' in loc:
            sticket = urllib.parse.unquote(loc.split('ticket=')[1].split('&')[0])
            break
        if r.status_code in (301, 302, 307, 308) and loc:
            url = loc
        else:
            break
    if not sticket:
        raise Exception("登录失败：无法获取票据参数")

    # Step 9: 转换票证为 CD code
    str1, str2 = transform(sticket)
    CD = f"CD-{str1}-{str2}-wiie://777.643.675.751:3537/rph"

    # Step 10: 调用 of.swu.edu.cn 回调
    url = f"https://of.swu.edu.cn/cas/oauth/callback/SWU_CAS2_FEDERAL?code={CD}@@hxbeat&state={state}"
    response = session.get(url, allow_redirects=True, timeout=timeout)

    if "ticket=" not in response.url:
        raise Exception("登录失败：无法获取ST参数")
    ST = response.url.split("ticket=")[1]

    # Step 11: 兑换 token
    token_response = requests.get(
        f"https://of.swu.edu.cn/gateway/fighter-middle/api/integrate/uaap/cas/exchange-token?token={ST}&remember=true",
        timeout=timeout
    ).json()
    if "data" not in token_response:
        raise Exception("登录失败：无法获取访问令牌")

    return token_response["data"]


def get_student_id(token, timeout=10):
    url = "https://of.swu.edu.cn/gateway/fighter-middle/api/auth/user?appType=fighter-portal"
    headers = {"fighter-auth-token": token}
    student_id = requests.get(url, headers=headers, timeout=timeout).json()["data"]["subject"]["username"]
    return student_id


def get_dormitory(token, timeout=10):
    url = "https://of.swu.edu.cn/gateway/fighter-baida/api/cqlc/getDormitory"
    headers = {"fighter-auth-token": token, "Content-Type": "application/json;charset=UTF-8"}
    response = requests.post(url, headers=headers, data=json.dumps({}), timeout=timeout)
    return response.json()


def get_transition_today(token, timeout=10):
    url = "https://of.swu.edu.cn//gateway/fighter-baida/api/cqtj/getTransitionByToday"
    headers = {"fighter-auth-token": token}
    data = {"pageNum": 1, "pageSize": 1}
    response = requests.post(url, headers=headers, data=data, timeout=timeout).json()["data"]["records"]
    return response[0] if response else None
