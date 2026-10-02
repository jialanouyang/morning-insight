"""内置信息源清单（对应产品需求文档 5.2「数据源完整清单」）。

分两部分：

1. `DEFAULT_SOURCES` —— 开箱默认启用的源。按文档验收标准「信息源默认全选」：
   全部 RSS 源 + 实测可用的网页源/API 源（已内置选择器或字段映射）；
   失效源在抓取层被独立容错、不影响其他源；需 JS 渲染的源留在目录中
   供一键添加（需安装 Playwright）。
2. `SOURCE_CATALOG` —— 文档要求的完整清单（中英文权威媒体、政府与机构、
   行业数据库、社交社区、行业协会、企业官方、学术与专利、人才情报）。
   带 `verified` 标记：
   - verified=True  实测可抓取，可在设置页一键添加
   - verified=False 官方未提供 RSS / 有反爬，提供站点入口 + 说明，
                    可用「网页源 + CSS 选择器」或「AI 解析选择器」接入

可抓取性依赖部署网络环境，`verified` 仅代表开发环境实测结果。
"""
import urllib.parse

# --------------------------------------------------------------------------- #
# 一、核心默认源（实测可抓取，全部保留在新用户默认配置中）
# --------------------------------------------------------------------------- #
_CORE_SOURCES: list[dict] = [
    {"name": "IT之家", "type": "rss", "url": "https://www.ithome.com/rss/", "enabled": True,
     "priority": 8, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "少数派", "type": "rss", "url": "https://sspai.com/feed", "enabled": True,
     "priority": 6, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "InfoQ 中文", "type": "rss", "url": "https://www.infoq.cn/feed", "enabled": True,
     "priority": 6, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "Solidot 奇客", "type": "rss", "url": "https://www.solidot.org/index.rss", "enabled": True,
     "priority": 5, "tags": {"language": "zh", "region": "中国", "category": "社交社区"}},
    {"name": "爱范儿", "type": "rss", "url": "https://www.ifanr.com/feed", "enabled": True,
     "priority": 5, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "钛媒体", "type": "rss", "url": "https://www.tmtpost.com/rss.xml", "enabled": True,
     "priority": 5, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "界面新闻", "type": "rss", "url": "https://a.jiemian.com/index.php?m=article&a=rss", "enabled": True,
     "priority": 5, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "量子位", "type": "rss", "url": "https://www.qbitai.com/feed", "enabled": True,
     "priority": 6, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "经济观察报", "type": "rss", "url": "https://www.eeo.com.cn/rss.xml", "enabled": True,
     "priority": 5, "tags": {"language": "zh", "region": "中国", "category": "权威媒体"}},
    {"name": "Hacker News", "type": "rss", "url": "https://hnrss.org/frontpage", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "美国", "category": "社交社区"}},
    {"name": "TechCrunch", "type": "rss", "url": "https://techcrunch.com/feed/", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "美国", "category": "权威媒体"}},
    {"name": "The Verge", "type": "rss", "url": "https://www.theverge.com/rss/index.xml", "enabled": True,
     "priority": 6, "tags": {"language": "en", "region": "美国", "category": "权威媒体"}},
    {"name": "Ars Technica", "type": "rss", "url": "https://feeds.arstechnica.com/arstechnica/index", "enabled": True,
     "priority": 6, "tags": {"language": "en", "region": "美国", "category": "权威媒体"}},
    {"name": "Wired", "type": "rss", "url": "https://www.wired.com/feed/rss", "enabled": True,
     "priority": 6, "tags": {"language": "en", "region": "美国", "category": "权威媒体"}},
    {"name": "MIT Technology Review", "type": "rss", "url": "https://www.technologyreview.com/feed/", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "美国", "category": "权威媒体"}},
    {"name": "OpenAI News", "type": "rss", "url": "https://openai.com/blog/rss.xml", "enabled": True,
     "priority": 8, "tags": {"language": "en", "region": "美国", "category": "企业官方"}},
    {"name": "Google AI Blog", "type": "rss", "url": "https://blog.google/technology/ai/rss/", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "美国", "category": "企业官方"}},
    {"name": "DeepMind", "type": "rss", "url": "https://deepmind.google/blog/rss.xml", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "英国", "category": "企业官方"}},
    {"name": "SEC 新闻稿", "type": "rss", "url": "https://www.sec.gov/news/pressreleases.rss", "enabled": True,
     "priority": 8, "tags": {"language": "en", "region": "美国", "category": "政府与机构"}},
    {"name": "美联储", "type": "rss", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "enabled": True,
     "priority": 8, "tags": {"language": "en", "region": "美国", "category": "政府与机构"}},
    {"name": "欧洲央行", "type": "rss", "url": "https://www.ecb.europa.eu/rss/press.html", "enabled": True,
     "priority": 7, "tags": {"language": "en", "region": "欧盟", "category": "政府与机构"}},
    {"name": "欧盟委员会", "type": "rss", "url": "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
     "enabled": True, "priority": 7,
     "tags": {"language": "en", "region": "欧盟", "category": "政府与机构"}},
]

# --------------------------------------------------------------------------- #
# 二、完整清单（可一键添加）
# --------------------------------------------------------------------------- #
def _src(name, category, language, region, url="", type_="rss", verified=False, note="",
         priority=5, render_js=False, selectors=None, items_path="", field_map=None,
         params=None, headers=None, json_var="", url_template=""):
    entry = {
        "name": name,
        "category": category,
        "language": language,
        "region": region,
        "type": type_,
        "url": url,
        "enabled": False,
        "priority": priority,
        "verified": verified,
        "note": note,
        "tags": {"language": language, "region": region, "category": category},
    }
    if render_js:
        entry["render_js"] = True
    if items_path:
        entry["items_path"] = items_path
    if field_map:
        entry["field_map"] = field_map
    if params:
        entry["params"] = params
    if headers:
        entry["headers"] = headers
    if json_var:
        entry["json_var"] = json_var
    if url_template:
        entry["url_template"] = url_template
    entry.update(selectors or {})   # list_selector / title_selector / url_selector / date_selector ...
    return entry


SOURCE_CATALOG: list[dict] = [
    # ---------------- 中文 · 权威媒体（含实测可用的抓取配置） ----------------
    _src("新华社", "权威媒体", "zh", "中国", "https://www.news.cn/politics/", "web", verified=True,
         priority=9, note="新华网时政频道",
         selectors={"list_selector": "div.xpage-content-list div.column-center-item",
                    "title_selector": "a", "url_selector": "a@href"}),
    _src("人民日报", "权威媒体", "zh", "中国", "http://www.people.com.cn/", "web", verified=True,
         priority=9, note="人民网首页要闻（官方 RSS 已停更）",
         selectors={"list_selector": "ul.list6 li", "title_selector": "a", "url_selector": "a@href"}),
    _src("央视新闻", "权威媒体", "zh", "中国",
         "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/news_1.jsonp?cb=news",
         "api", verified=True, priority=9, note="央视新闻 JSON 接口（自动剥 JSONP 包装）",
         items_path="data.list",
         field_map={"title": "title", "url": "url", "summary": "brief", "published_at": "focus_date"}),
    _src("财新", "权威媒体", "zh", "中国", "https://www.caixin.com/", "web", verified=True, priority=8,
         note="首页要闻列表（部分深度内容需订阅）",
         selectors={"list_selector": "dt", "title_selector": "a", "url_selector": "a@href"}),
    _src("第一财经", "权威媒体", "zh", "中国", "https://www.yicai.com/news/", "web", verified=True,
         priority=8, note="要闻频道列表",
         selectors={"list_selector": "div.m-con", "title_selector": "a", "url_selector": "a@href"}),
    _src("经济观察报", "权威媒体", "zh", "中国", "https://www.eeo.com.cn/rss.xml", verified=True, priority=6),
    _src("36氪", "权威媒体", "zh", "中国", "https://m.36kr.com/newsflashes", "api",
         verified=True, priority=8,
         note="移动端快讯页内嵌 JSON 状态（桌面端有 WAF 检测）",
         headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                                "Mobile/15E148 Safari/604.1"},
         json_var="initialState",
         items_path="newsflashList.flow.itemList",
         field_map={"title": "templateMaterial.widgetTitle",
                    "summary": "templateMaterial.widgetContent",
                    "published_at": "templateMaterial.publishTime"},
         url_template="https://36kr.com/newsflashes/{itemId}"),
    _src("虎嗅", "权威媒体", "zh", "中国", "https://rss.huxiu.com/", verified=True, priority=7,
         note="官方全量 RSS"),
    _src("钛媒体", "权威媒体", "zh", "中国", "https://www.tmtpost.com/rss.xml", verified=True, priority=6),
    _src("界面新闻", "权威媒体", "zh", "中国", "https://a.jiemian.com/index.php?m=article&a=rss", verified=True, priority=6),
    _src("澎湃新闻", "权威媒体", "zh", "中国", "https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar",
         "api", verified=True, priority=8, note="首页热门新闻 JSON 接口",
         items_path="data.hotNews",
         field_map={"title": "name", "published_at": "pubTimeLong"},
         url_template="https://www.thepaper.cn/newsDetail_forward_{contId}"),
    _src("南方周末", "权威媒体", "zh", "中国", "https://www.infzm.com/", "web", verified=True, priority=7,
         note="首页文章列表（时间形如「1小时前」，按相对时间换算）",
         selectors={"list_selector": "article", "title_selector": "a", "url_selector": "a@href",
                    "date_selector": "footer span:last-child"}),
    # ---------------- 中文 · 政府与机构（含实测可用的抓取配置） ----------------
    _src("国务院", "政府与机构", "zh", "中国",
         "https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary_gw&q=&timetype=timeqb"
         "&mintime=&maxtime=&sort=pubtime&sortType=1&searchfield=title"
         "&pcodeJiguan=&childtype=&subchildtype=&tsbq=&pubtimeyear=&puborg="
         "&pcodeYear=&pcodeNum=&filetype=&p=1&n=20&inpro=&bmfl=&dup=&orpro=",
         "api", verified=True, priority=10, note="国务院政策文件库搜索接口（按发布时间倒序）",
         items_path="searchVO.listVO",
         field_map={"title": "title", "url": "url", "summary": "summary", "published_at": "pubtimeStr"},
         headers={"Referer": "https://sousuo.www.gov.cn/", "Accept": "application/json, text/plain, */*"}),
    _src("国家发改委", "政府与机构", "zh", "中国", "https://www.ndrc.gov.cn/xwdt/xwfb/", "web",
         verified=True, priority=10, note="新闻发布列表",
         selectors={"list_selector": "ul.u-list li", "title_selector": "a",
                    "url_selector": "a@href", "date_selector": "span"}),
    _src("工业和信息化部", "政府与机构", "zh", "中国", "https://www.miit.gov.cn/xwdt/gxdt/sjdt/", "web",
         render_js=True, priority=10, note="官网列表由 JS 加载且直连超时，需 Playwright 后启用"),
    _src("科学技术部", "政府与机构", "zh", "中国", "https://www.most.gov.cn/kjbgz/", "web",
         verified=True, priority=9, note="科技工作动态",
         selectors={"list_selector": "ul.info_list2 li", "title_selector": "a", "url_selector": "a@href",
                    "date_selector": "span.date"}),
    _src("商务部", "政府与机构", "zh", "中国", "http://www.mofcom.gov.cn/article/ae/", "web",
         render_js=True, priority=9, note="官网有反爬（502/跳转移动端），需 Playwright 后启用"),
    _src("财政部", "政府与机构", "zh", "中国", "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/", "web",
         verified=True, priority=9, note="财政新闻列表",
         selectors={"list_selector": "ul.xwfb_listbox li", "title_selector": "a", "url_selector": "a@href",
                    "date_selector": "span"}),
    _src("中国人民银行", "政府与机构", "zh", "中国",
         "http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html", "web",
         verified=True, priority=10, note="交流沟通·新闻列表",
         selectors={"list_selector": "font.newslist_style", "title_selector": "a", "url_selector": "a@href"}),
    _src("中国证监会", "政府与机构", "zh", "中国", "http://www.csrc.gov.cn/", "web",
         verified=True, priority=10, note="官网首页·新闻发布区（li.li-height 为新闻项，导航 li 已排除）",
         selectors={"list_selector": "div.ywfb-box li.li-height", "title_selector": "a",
                    "url_selector": "a@href", "date_selector": "span.time"}),
    _src("国家金融监督管理总局", "政府与机构", "zh", "中国", "https://www.nfra.gov.cn/", "web",
         render_js=True, priority=9, note="官网首页为 JS 脚本壳，需 Playwright + AI 解析选择器后启用"),
    _src("国家统计局", "政府与机构", "zh", "中国", "https://www.stats.gov.cn/sj/zxfb/", "web",
         verified=True, priority=9, note="最新发布列表",
         selectors={"list_selector": "div.list-content li", "title_selector": "a", "url_selector": "a@href",
                    "date_selector": "span"}),
    _src("国家知识产权局", "政府与机构", "zh", "中国", "https://www.cnipa.gov.cn/col/col75/index.html", "web",
         priority=8, note="栏目列表由 JS 加载，需 Playwright + AI 解析选择器后启用"),
    _src("中国信通院", "政府与机构", "zh", "中国", "http://www.caict.ac.cn/kxyj/qwfb/", "web",
         priority=8, note="站点有反爬（412），需配置请求头或浏览器渲染"),
    _src("赛迪顾问", "政府与机构", "zh", "中国", "https://www.ccidconsulting.com/", "web",
         priority=7, note="官网为 JS 站点，需 Playwright 后启用"),
    # ---------------- 中国港澳台 ----------------
    _src("香港金融管理局 HKMA", "政府与机构", "en", "中国香港", "https://www.hkma.gov.hk/eng/news-and-media/press-releases/", "web", note="官网无 RSS，可用网页源接入", priority=8),
    _src("香港交易所 HKEX", "政府与机构", "en", "中国香港", "https://www.hkex.com.hk/News/News-Release", "web", note="官网无 RSS，可用网页源接入", priority=8),
    _src("南华早报 SCMP", "权威媒体", "en", "中国香港", "https://www.scmp.com/rss/91/feed", note="部分地区网络受限，可尝试网页源", priority=7),
    _src("DigiTimes", "权威媒体", "en", "中国台湾", "https://www.digitimes.com/rss/daily.xml", note="部分内容需订阅", priority=7),
    _src("工商时报", "权威媒体", "zh", "中国台湾", "https://ctee.com.tw/", "web", note="官网无 RSS，可用网页源接入", priority=6),
    # ---------------- 行业数据库 ----------------
    _src("IT 桔子", "行业数据库", "zh", "中国", "https://www.itjuzi.com/", "web", note="需登录，建议用 API 源接入", priority=8),
    _src("企查查", "行业数据库", "zh", "中国", "https://www.qcc.com/", "web", note="需登录，建议用 API 源接入", priority=7),
    _src("天眼查", "行业数据库", "zh", "中国", "https://www.tianyancha.com/", "web", note="需登录，建议用 API 源接入", priority=7),
    _src("启信宝", "行业数据库", "zh", "中国", "https://www.qixin.com/", "web", note="需登录，建议用 API 源接入", priority=6),
    _src("投中网", "行业数据库", "zh", "中国", "https://www.chinaventure.com.cn/", "web", note="官网无 RSS，可用网页源接入", priority=7),
    _src("清科研究", "行业数据库", "zh", "中国", "https://research.pedaily.cn/", "web", note="官网无 RSS，可用网页源接入", priority=7),
    # ---------------- 社交社区（中文） ----------------
    _src("知乎", "社交社区", "zh", "中国", "https://www.zhihu.com/", "web", note="无公开 RSS，可用网页源接入", priority=5),
    _src("微博热搜", "社交社区", "zh", "中国", "https://s.weibo.com/top/summary", "web", note="无公开 RSS，可用网页源接入", priority=5),
    _src("雪球", "社交社区", "zh", "中国", "https://xueqiu.com/hots/topic/rss", verified=True, priority=6),
    _src("即刻", "社交社区", "zh", "中国", "https://web.okjike.com/", "web", note="无公开 RSS，可用网页源接入", priority=4),
    # ---------------- 行业协会 ----------------
    _src("中国人工智能学会", "行业协会", "zh", "中国", "https://www.caai.cn/", "web", note="官网无 RSS，可用网页源接入", priority=6),
    _src("中国半导体行业协会", "行业协会", "zh", "中国", "http://www.csia.net.cn/", "web", note="官网无 RSS，可用网页源接入", priority=6),
    # ---------------- 学术与专利（技术情报） ----------------
    _src("知领·中国工程科技", "学术与专利", "zh", "中国", "https://www.ckcest.cn/", "web", verified=True, priority=7,
         note="中国工程院·工程科技知识中心（原「知领」），智库观点与工程科技新闻",
         selectors={"list_selector": "a[href*='news/detail']", "title_selector": "", "url_selector": "@href"}),
    _src("arXiv · 人工智能", "学术与专利", "en", "国际", "http://export.arxiv.org/rss/cs.AI",
         verified=True, priority=8, note="AI 领域每日新论文与预印本"),
    _src("arXiv · 机器学习", "学术与专利", "en", "国际", "http://export.arxiv.org/rss/cs.LG",
         verified=True, priority=7, note="机器学习每日新论文与预印本"),
    _src("arXiv · 自然语言处理", "学术与专利", "en", "国际", "http://export.arxiv.org/rss/cs.CL",
         verified=True, priority=6, note="NLP 每日新论文与预印本"),
    _src("Nature 新闻", "学术与专利", "en", "英国", "https://www.nature.com/nature.rss",
         verified=True, priority=7, note="《自然》最新研究要闻"),
    _src("IEEE Spectrum", "学术与专利", "en", "美国", "https://spectrum.ieee.org/feeds/feed.rss",
         verified=True, priority=6, note="IEEE 综合科技媒体（电子/通信/AI）"),
    _src("科讯头条（PubScholar）", "学术与专利", "zh", "中国", "https://pubscholar.cn/headlines", "web",
         render_js=True, priority=8, note="中科院文献情报体系 AI 挖掘 JCR Q1 期刊与 1000+ 官网、每日推荐科研突破；网页为 JS 渲染，安装 Playwright 后可用"),
    _src("Lens.org", "学术与专利", "en", "国际", "https://www.lens.org/", "web",
         note="1.7 亿专利 + 3.25 亿学术作品聚合；免费层需注册 API Token，建议用 API 源接入", priority=7),
    _src("EPO TIP / PATSTAT", "学术与专利", "en", "欧盟", "https://www.epo.org/en/searching-for-patents/data", "web",
         note="欧洲专利局全球专利数据平台（含 Deep Tech Finder 深科技初创发现）；需注册，官网有反爬", priority=6),
    _src("Deep Tech Finder", "学术与专利", "en", "欧盟", "https://www.deeptechfinder.epo.org/", "web",
         note="EPO 工具：发现拥有专利创新的欧洲深科技初创与高校；需注册", priority=5),
    _src("SpecialSci", "学术与专利", "zh", "中国", "https://www.specialsci.cn/", "web",
         note="国道外文专题数据库，1995 年以来欧美科技文献；需机构订阅", priority=6),
    _src("IEEE Xplore", "学术与专利", "en", "美国", "https://ieeexplore.ieee.org/", "web",
         note="电子电气/通信/计算机权威文献库；需订阅（免费替代：IEEE Spectrum RSS 已内置）", priority=6),
    _src("GitScholar", "学术与专利", "en", "国际", "https://huggingface.co/datasets/huawei-csl/GitScholar", "web",
         note="链接 44 万 GitHub 仓库与 55 万 AI 论文的数据集，用于预测研究影响力；非实时源", priority=4),
    # ---------------- 人才情报 ----------------
    _src("企名片", "人才情报", "zh", "中国", "https://www.qimingpian.com/", "web",
         render_js=True, priority=7, note="科技创新项目/机构/人才变动追踪；网页为 JS 渲染（Nuxt），安装 Playwright 后可用"),
    _src("智联招聘·就业市场报告", "人才情报", "zh", "中国", "https://www.zhaopin.com/", "web",
         note="行业就业景气与供需报告；主要经公众号/白皮书发布，官网无公开列表，可用网页源自助接入", priority=6),
    _src("Hacker News 招聘", "人才情报", "en", "美国", "https://hnrss.org/jobs",
         verified=True, priority=5, note="「Ask HN: Who is hiring」月度帖的招聘评论，反映创业公司用人动向"),
    _src("Lusha", "人才情报", "en", "以色列", "https://www.lusha.com/", "web",
         note="B2B 联系人实时信号（职位变动/晋升/招聘激增）；需 API Key，建议 API 源接入", priority=5),
    _src("Lightcast", "人才情报", "en", "美国", "https://lightcast.io/", "web",
         note="基于招聘广告的劳动力市场数据（人才迁移与流失）；需订阅", priority=6),
    _src("Zeki Talent Alpha", "人才情报", "en", "英国", "https://zekidata.com/", "web",
         note="追踪全球 3 万+ 公司深科技人才流动（斯坦福 AI Index 数据来源之一）；需订阅", priority=6),
    _src("Coresignal", "人才情报", "en", "立陶宛", "https://coresignal.com/", "web",
         note="B2B 社交帖子分析：招聘活动与高管加入新公司信号；需 API Key，建议 API 源接入", priority=5),
    _src("Mercer Workforce", "人才情报", "en", "美国", "https://www.mercer.com/", "web",
         note="全球员工流动趋势/离职率/热门技能监控；需订阅", priority=4),
    # ---------------- 英文 · 权威媒体 ----------------
    _src("Reuters", "权威媒体", "en", "国际", "https://www.reuters.com/", "web", note="官方无公开 RSS，建议网页源或第三方 RSS 网关", priority=9),
    _src("Bloomberg", "权威媒体", "en", "美国", "https://feeds.bloomberg.com/markets/news.rss", note="部分地区网络受限", priority=9),
    _src("Financial Times", "权威媒体", "en", "英国", "https://www.ft.com/?format=rss", note="部分地区网络受限；部分内容需订阅", priority=9),
    _src("The Wall Street Journal", "权威媒体", "en", "美国", "https://feeds.a.dj.com/rss/RSSWSJD.xml", verified=True, priority=9),
    _src("The New York Times", "权威媒体", "en", "美国", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", note="部分地区网络受限", priority=8),
    _src("BBC", "权威媒体", "en", "英国", "https://feeds.bbci.co.uk/news/business/rss.xml", note="部分地区网络受限", priority=8),
    _src("CNBC", "权威媒体", "en", "美国", "https://www.cnbc.com/id/100003114/device/rss/rss.html", priority=8),
    _src("The Economist", "权威媒体", "en", "英国", "https://www.economist.com/finance-and-economics/rss.xml", note="部分地区网络受限；部分内容需订阅", priority=8),
    _src("TechCrunch", "权威媒体", "en", "美国", "https://techcrunch.com/feed/", verified=True, priority=7),
    _src("The Verge", "权威媒体", "en", "美国", "https://www.theverge.com/rss/index.xml", verified=True, priority=7),
    _src("Wired", "权威媒体", "en", "美国", "https://www.wired.com/feed/rss", verified=True, priority=7),
    _src("Ars Technica", "权威媒体", "en", "美国", "https://feeds.arstechnica.com/arstechnica/index", verified=True, priority=7),
    _src("VentureBeat", "权威媒体", "en", "美国", "https://venturebeat.com/feed/", note="有频率限制，可重试", priority=7),
    _src("Nikkei Asia", "权威媒体", "en", "日本", "https://asia.nikkei.com/rss/feed/nar", note="部分地区网络受限", priority=8),
    _src("南华早报 SCMP", "权威媒体", "en", "中国香港", "https://www.scmp.com/rss/91/feed", note="部分地区网络受限", priority=7),
    _src("The Information", "权威媒体", "en", "美国", "https://www.theinformation.com/feed", "web", note="需订阅", priority=7),
    _src("Semafor", "权威媒体", "en", "美国", "https://www.semafor.com/rss.xml", priority=6),
    _src("Axios", "权威媒体", "en", "美国", "https://api.axios.com/feed/", priority=6),
    # ---------------- 英文 · 政府与机构 ----------------
    _src("美国 SEC", "政府与机构", "en", "美国", "https://www.sec.gov/news/pressreleases.rss", verified=True, priority=9),
    _src("美国白宫", "政府与机构", "en", "美国", "https://www.whitehouse.gov/feed/", "web", note="RSS 路径已调整，可用网页源接入", priority=9),
    _src("美国商务部", "政府与机构", "en", "美国", "https://www.commerce.gov/news/press-releases", "web", note="有反爬，建议网页源或 API", priority=8),
    _src("美国财政部", "政府与机构", "en", "美国", "https://home.treasury.gov/rss/press.xml", priority=8),
    _src("美联储", "政府与机构", "en", "美国", "https://www.federalreserve.gov/feeds/press_all.xml", verified=True, priority=9),
    _src("美联储 FOMC", "政府与机构", "en", "美国", "https://www.federalreserve.gov/feeds/press_monetary.xml", verified=True, priority=9),
    _src("USPTO", "政府与机构", "en", "美国", "https://www.uspto.gov/news", "web", note="RSS 路径已调整，可用网页源接入", priority=7),
    _src("DARPA", "政府与机构", "en", "美国", "https://www.darpa.mil/news", "web", note="无 RSS，可用网页源接入", priority=6),
    _src("NIST", "政府与机构", "en", "美国", "https://www.nist.gov/news-events/news/rss.xml", verified=True, priority=7),
    _src("FDA", "政府与机构", "en", "美国", "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml", "web", note="RSS 路径调整频繁，建议网页源", priority=7),
    _src("FCC", "政府与机构", "en", "美国", "https://www.fcc.gov/news-events/headlines", "web", note="无 RSS，可用网页源接入", priority=6),
    _src("FTC", "政府与机构", "en", "美国", "https://www.ftc.gov/feeds/press-release.xml", note="有反爬（403），可尝试网页源", priority=7),
    _src("欧盟委员会", "政府与机构", "en", "欧盟", "https://ec.europa.eu/commission/presscorner/api/rss?language=en", verified=True, priority=8),
    _src("欧洲央行 ECB", "政府与机构", "en", "欧盟", "https://www.ecb.europa.eu/rss/press.html", verified=True, priority=8),
    _src("英国政府", "政府与机构", "en", "英国", "https://www.gov.uk/government/announcements.atom", priority=7),
    _src("英国 FCA", "政府与机构", "en", "英国", "https://www.fca.org.uk/news/rss.xml", note="有反爬（403），可尝试网页源", priority=7),
    _src("UK IPO", "政府与机构", "en", "英国", "https://www.gov.uk/government/organisations/intellectual-property-office.atom", priority=6),
    _src("德国联邦财政部 BMF", "政府与机构", "en", "德国", "https://www.bundesfinanzministerium.de/EN/RSS/rss_node.html", priority=6),
    _src("法国 DGE", "政府与机构", "en", "法国", "https://www.entreprises.gouv.fr/", "web", note="无 RSS，可用网页源接入", priority=5),
    _src("日本 METI", "政府与机构", "en", "日本", "https://www.meti.go.jp/english/press/", "web", note="有反爬，建议网页源接入", priority=7),
    _src("韩国 MSIT", "政府与机构", "en", "韩国", "https://www.msit.go.kr/eng/", "web", note="无 RSS，可用网页源接入", priority=6),
    _src("新加坡 MAS", "政府与机构", "en", "新加坡", "https://www.mas.gov.sg/news", "web", note="无 RSS，可用网页源接入", priority=7),
    _src("印度 MeitY", "政府与机构", "en", "印度", "https://www.meity.gov.in/", "web", note="无 RSS，可用网页源接入", priority=5),
    # ---------------- 国际组织 ----------------
    _src("IMF", "政府与机构", "en", "国际组织", "https://www.imf.org/en/News/RSS?language=eng", note="有反爬（403），可尝试网页源", priority=8),
    _src("World Bank", "政府与机构", "en", "国际组织", "https://www.worldbank.org/en/news/all?format=rss", priority=7),
    _src("WTO", "政府与机构", "en", "国际组织", "https://www.wto.org/library/rss/latest_news_e.xml", priority=6),
    _src("OECD", "政府与机构", "en", "国际组织", "https://www.oecd.org/newsroom/rss.xml", note="有反爬（403），可尝试网页源", priority=7),
    _src("BIS", "政府与机构", "en", "国际组织", "https://www.bis.org/doclist/all_pressrels.rss", priority=7),
    _src("FSB", "政府与机构", "en", "国际组织", "https://www.fsb.org/feed/", verified=True, priority=7),
    _src("IEA", "政府与机构", "en", "国际组织", "https://www.iea.org/rss/news", note="有反爬（403），可尝试网页源", priority=6),
    _src("WHO", "政府与机构", "en", "国际组织", "https://www.who.int/rss-feeds/news-english.xml", verified=True, priority=7),
    _src("UNCTAD", "政府与机构", "en", "国际组织", "https://unctad.org/rss.xml", note="有反爬（403），可尝试网页源", priority=5),
    # ---------------- 英文 · 行业数据库 ----------------
    _src("Crunchbase News", "行业数据库", "en", "美国", "https://news.crunchbase.com/feed/", priority=8),
    _src("PitchBook", "行业数据库", "en", "美国", "https://pitchbook.com/news", "web", note="需订阅，建议网页源或 API", priority=7),
    _src("CB Insights", "行业数据库", "en", "美国", "https://www.cbinsights.com/research/feed/", priority=7),
    _src("Dealroom", "行业数据库", "en", "欧盟", "https://dealroom.co/blog/feed/", priority=5),
    _src("Tracxn", "行业数据库", "en", "印度", "https://tracxn.com/", "web", note="需订阅", priority=5),
    _src("Statista", "行业数据库", "en", "德国", "https://www.statista.com/rss/", "web", note="需订阅", priority=5),
    _src("GlobalData", "行业数据库", "en", "英国", "https://www.globaldata.com/feed/",
         verified=True, priority=6, note="颠覆性技术（AI/区块链等）与细分市场研究新闻"),
    _src("Marketline", "行业数据库", "en", "英国", "https://marketline.com/", "web", note="细分市场深度研究报告；需订阅", priority=5),
    _src("Plunkett Research", "行业数据库", "en", "美国", "https://plunkettresearch.com/", "web", note="30+ 热门行业分析/趋势/统计/竞争情报；需订阅", priority=5),
    _src("Speeda Business Insights", "行业数据库", "en", "日本", "https://www.speeda.com/", "web", note="AI/量子计算等热门趋势即时见解；需订阅", priority=6),
    _src("国研网", "行业数据库", "zh", "中国", "https://www.drcnet.com.cn/", "web",
         note="国务院发展研究中心旗下，战略性新兴产业与未来产业数据库；需机构订阅", priority=7),
    _src("Explorium", "行业数据库", "en", "以色列", "https://explorium.ai/", "web",
         note="外部数据平台：公司融资/员工变化/并购实时追踪；需 API Key，建议 API 源接入", priority=5),
    _src("RESSET", "行业数据库", "zh", "中国", "https://www.resset.com/", "web",
         note="金融研究数据库，公司融资与并购数据；需订阅", priority=5),
    _src("Veridion", "行业数据库", "en", "罗马尼亚", "https://veridion.com/", "web",
         note="企业画像数据（新办公地点/招聘激增等竞争对手动向信号）；需 API Key，建议 API 源接入", priority=5),
    # ---------------- 英文 · 社交社区 ----------------
    _src("X (Twitter)", "社交社区", "en", "美国", "https://x.com/", "web", note="无公开 RSS，需 API 或第三方网关", priority=5),
    _src("Reddit", "社交社区", "en", "美国", "https://www.reddit.com/r/technology/.rss", note="部分地区网络受限", priority=6),
    _src("Hacker News", "社交社区", "en", "美国", "https://hnrss.org/frontpage", verified=True, priority=7),
    _src("GitHub Trending", "社交社区", "en", "美国", "https://github.com/trending", "web", verified=True,
         priority=7, note="GitHub 每日热门项目（按星标增长），开源技术趋势信号",
         selectors={"list_selector": "article.Box-row", "title_selector": "h2 a",
                    "url_selector": "h2 a@href", "summary_selector": "p"}),
    _src("LinkedIn", "社交社区", "en", "美国", "https://www.linkedin.com/", "web", note="无公开 RSS，需 API", priority=4),
    _src("Product Hunt", "社交社区", "en", "美国", "https://www.producthunt.com/feed", verified=True, priority=6),
    _src("Substack", "社交社区", "en", "美国", "https://substack.com/", "web", note="可按订阅号单独添加 RSS", priority=5),
    _src("Medium", "社交社区", "en", "美国", "https://medium.com/feed/tag/technology", note="部分地区网络受限", priority=5),
    _src("Quora", "社交社区", "en", "美国", "https://www.quora.com/", "web", note="无公开 RSS", priority=3),
    _src("Blind", "社交社区", "en", "韩国", "https://www.teamblind.com/", "web", note="无公开 RSS，需登录", priority=3),
    # ---------------- 企业官方（AI / 科技） ----------------
    _src("OpenAI News", "企业官方", "en", "美国", "https://openai.com/blog/rss.xml", verified=True, priority=8),
    _src("Google AI Blog", "企业官方", "en", "美国", "https://blog.google/technology/ai/rss/", verified=True, priority=7),
    _src("DeepMind", "企业官方", "en", "英国", "https://deepmind.google/blog/rss.xml", verified=True, priority=7),
]


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _derive_default_sources() -> list[dict]:
    """按文档验收标准「信息源默认全选」生成默认源。

    规则：
    - 全部 RSS/Atom 源默认启用（失效源由抓取层独立容错）；
    - 网页源 / API 源：仅「实测可用（verified）且不需要 JS 渲染」的默认启用
      （这些源已内置选择器 / 字段映射，开箱即用）；
    - 其余网页源（需 Playwright 或需配选择器）留在目录中供一键添加。
    """
    seen_urls = {s.get("url") for s in _CORE_SOURCES}
    seen_names = {s.get("name") for s in _CORE_SOURCES}
    merged: list[dict] = [dict(s) for s in _CORE_SOURCES]
    for item in SOURCE_CATALOG:
        stype = item.get("type") or "rss"
        if not item.get("url"):
            continue
        if stype == "rss":
            include = True
        else:
            include = bool(item.get("verified")) and not item.get("render_js")
        if not include:
            continue
        if item["name"] in seen_names or item["url"] in seen_urls:
            continue
        entry = {k: v for k, v in item.items() if k not in ("verified", "note")}
        entry["enabled"] = True
        entry.setdefault("tags", {})
        merged.append(entry)
        seen_urls.add(item["url"])
        seen_names.add(item["name"])
    return sorted(merged, key=lambda s: -int(s.get("priority") or 0))


DEFAULT_SOURCES: list[dict] = _derive_default_sources()


def build_google_news_url(keyword: str, lang: str = "zh") -> str:
    """用关键词生成 Google News RSS 链接（海外网络可达时使用）。"""
    if lang.startswith("zh"):
        hl, gl, ceid = "zh-CN", "CN", "CN:zh-Hans"
    else:
        hl, gl, ceid = "en-US", "US", "US:en"
    return (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(keyword)}&hl={hl}&gl={gl}&ceid={ceid}"
    )


def build_360_news_url(keyword: str) -> str:
    """用关键词生成 360 资讯搜索链接（服务端渲染，国内网络可达）。"""
    return f"https://news.so.com/ns?q={urllib.parse.quote(keyword)}"


# 搜索引擎索引：关键词建源的后端清单（「信息源获取可通过搜索引擎索引」）
SEARCH_ENGINES: dict[str, dict] = {
    "so360": {
        "label": "360 资讯搜索",
        "accessible": "CN",
        "doc": "服务端渲染，国内网络可达；返回带日期的新闻结果",
    },
    "google": {
        "label": "Google News",
        "accessible": "海外网络",
        "doc": "官方 RSS；国内网络通常不可达",
    },
}


def keyword_source(keyword: str, lang: str = "zh", engine: str = "so360") -> dict:
    """按关键词构造一个搜索引擎索引信息源（用于行业关键词自动建源）。

    engine:
    - "so360"  360 资讯搜索（默认，国内可达，返回服务端渲染的新闻结果）
    - "google" Google News RSS（海外网络可达时使用）
    """
    if engine == "google":
        return {
            "name": f"关键词·{keyword}",
            "type": "rss",
            "url": build_google_news_url(keyword, lang),
            "enabled": True,
            "priority": 6,
            "tags": {"language": lang, "region": "国际", "category": "关键词源"},
        }
    return {
        "name": f"关键词·{keyword}",
        "type": "web",
        "url": build_360_news_url(keyword),
        "enabled": True,
        "priority": 6,
        "list_selector": "li.res-list",
        "title_selector": "a@title",
        "url_selector": "a@href",
        "summary_selector": "p.summary",
        "date_selector": "span.time",
        "tags": {"language": lang, "region": "中国", "category": "关键词源"},
    }


def catalog_by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in SOURCE_CATALOG:
        grouped.setdefault(item["category"], []).append(item)
    return grouped


def source_templates() -> list[dict]:
    """给前端「添加信息源」用的空白模板。"""
    return [
        {"type": "rss", "label": "RSS / Atom", "fields": ["name", "url"],
         "doc": "最简方式：粘贴 RSS 链接即可"},
        {"type": "api", "label": "API 接口", "fields":
            ["name", "url", "method", "api_key", "api_key_header", "api_key_query",
             "params", "items_path", "field_map", "base_url"],
         "doc": "需要 Key 时填写；items_path 指向列表，field_map 做字段映射"},
        {"type": "web", "label": "网页源", "fields":
            ["name", "url", "list_selector", "title_selector", "url_selector",
             "summary_selector", "date_selector", "base_url", "render_js"],
         "doc": "填 CSS 选择器；不确定时可点「AI 解析选择器」自动推断"},
    ]
