import re
import requests
import urllib.parse
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


def verify(username, password, timeout=10):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    session.trust_env = False
    base_url = "https://idm.swu.edu.cn"

    # Step 1: 跟随到 uaaap 登录页
    response = session.get(
        "https://of.swu.edu.cn/cas/oauth/login/SWU_CAS2_FEDERAL?service="
        "https%3A%2F%2Fof.swu.edu.cn%2Fgateway%2Ffighter-middle%2Fapi%2Fintegrate%2Fuaap"
        "%2Fcas%2Fresolve-cas-return%3Fnext%3Dhttps%253A%252F%252Fof.swu.edu.cn%252F%2523"
        "%252FcasLogin%253Ffrom%253D%25252FappCenter",
        allow_redirects=True, timeout=timeout
    )
    service = urllib.parse.parse_qs(urllib.parse.urlparse(response.url).query)['service'][0]

    # Step 2: federalEnable → idm 登录页
    response = session.get(
        f"https://uaaap.swu.edu.cn/cas/login?service={urllib.parse.quote(service)}&federalEnable=true",
        allow_redirects=False, timeout=timeout
    )
    response = session.get(response.headers['Location'], allow_redirects=True, timeout=timeout)

    # Step 3: 提取参数
    random_key = re.search(r'id="random"[^>]*value="([^"]+)"', response.text).group(1)
    goto = re.search(r'name="goto"[^>]*value="([^"]+)"', response.text).group(1)
    sunqp = re.search(r'name="SunQueryParamsString"[^>]*value="([^"]+)"', response.text).group(1)

    # Step 4: 验证码 + 加密
    code = _solve_captcha(session, base_url, timeout)
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

    response = session.post(f"{base_url}/am/UI/Login", data=data, allow_redirects=False, timeout=timeout)
    if response.status_code != 302:
        return None
    return response
