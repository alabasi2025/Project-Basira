# برومت للوكيل المطوِّر — دمج تصميم «البصيرة» (UI v3) في مستودع بصيرة

> أنت الوكيل المطوِّر لمشروع بصيرة. هذه الحزمة فيها عمل وكيل تصميم سابق (Claude) على فرع `design/claude`.
> مهمتك: **تسحبها، تتحقق منها بالقياس، وتدمجها بنفسك** وفق قواعد `CLAUDE.md` / `AGENTS.md` (لا PR؛ أنت تدمج في `main` ثم تتحقق بعد الدمج).
> اقرأ أولًا: `START_HERE_NEXT_AGENT.md` → `docs/STATE.md` → `docs/DECISIONS.md`. لا تتجاوز أي خط أحمر.

---

## 1. ماذا سُوّي (ملخص)

**القاعدة:** الحزمة مبنية فوق `main` @ `ee5633f` (أُعيد التأسيس عليه) — طرف الفرع `design/claude` @ `54e24ff0ca0b9b29d02101b1c330aa452163f486` (commitان، 29 ملفًا، +4641/−197).

واجهة جديدة كاملة باسم مفهوم **«البصيرة»**: منصة متعددة الصفحات بدل صفحة واحدة، والخطّاف أن **المنتج يعمل أمام الزائر** خلال الثواني الأولى.

| المسار | المحتوى |
|---|---|
| `/` | الرئيسية: «العدسة» — منشور حقيقي + **استجابة `/v1/check` مسجّلة حرفيًا من المحرك** (الحالات الأربع كلها). حلقة ضوء تمر على كل اقتباس فيضيء بحالته، وكلمة المصدر تظهر في إطار ذهبي فوق كلمة المستخدم المختلفة. زر «شغّله حيًا» يعيد الفحص على المحرك. ثم: كيف يعمل (دور الذكاء الاصطناعي / دور المحرك)، الحالات الأربع، الخدمات، CTA |
| `/check` | مساحة التحقق: أوضاع نص عربي + صورة (يعملان) / اقتباس إنجليزي + الحارس (**«قريبًا» — لا يستدعيان المحرك أبدًا**). بعد كل فحص شريط «ما الذي حدث في هذا الفحص»: الذكاء الاصطناعي (النموذج + الزمن) ← المحرك الحتمي ← المدقق اللاحق + إصدارات المصادر. ورشة النتائج القديمة (E-042) مُعاد استخدامها كما هي |
| `/services` | كل الخدمات بحالتها الحقيقية: يعمل الآن / قريبًا |
| `/developers` | أمثلة curl/JS، جدول المسارات الحية، عقد الاستجابة، MCP (موسوم «قيد البناء») |
| `/trust` (+ `#sources` + `#limits`، و`/limits` يحوّل إليها) | 9 أرقام **مولّدة آليًا** من تقارير المستودع مع رابط الملف والسطر، المنهجية، المصادر حيّة من `/v1/sources`، صفحة «حدودنا» |
| `/about` | الهوية، المسابقة، الإفصاح عن الذكاء الاصطناعي، المبادئ |

**الملفات الجديدة الأساسية:**
- `frontend/src/site/` — `strings.ts` (نصوص المنصة ar/en، بلا نص ديني ولا أرقام)، `router.ts` (History API بلا مكتبة)، `Shell.tsx` (رأس/قائمة جوال/تذييل)، `Home.tsx`، `LensDemo.tsx`، `Starfield.tsx` (WebGL)، `Pages.tsx`، `services.ts`، `hooks.ts`، `lux.css` (طبقة التصميم)، `site.test.tsx`
- `frontend/src/__generated__/` — `hero.json`، `examples.json`، `trust.json` (**مولّدة، لا تُحرَّر يدويًا**)
- `scripts/gen_examples.py` — يبني الأمثلة من `eval/cases.yaml` + `scripts/smoke.py`، و`--record URL` يسجّل استجابة الرئيسية من المحرك الحي
- `scripts/gen_trust.py` — يستخرج الأرقام من `eval/REPORT.md` و`eval/islamiceval/REPORT_*.md` مع الملف والسطر
- `scripts/check_site_lexicon.py` — يمرّر كل نصوص الواجهة على ماسح المعجم الممنوع في الباك إند (`app.messages.scan_forbidden`)
- `frontend/public/sw.js` — PWA shell، **لا يخزّن `/v1/*` ولا `/health` أبدًا**
- `ecosystem.config.cjs` — API على :8000 (يقدّم `frontend/dist`)، معاينة UI على :3000

**ملفات معدّلة:** `App.tsx` (توجيه + تحميل كسول)، `Check.tsx` (أعيدت كتابته على نفس العقد)، `Check.test.tsx`، `i18n.ts` (حُذفت آية مكتوبة باليد كانت في placeholder — كانت خرقًا للخط الأحمر)، `main.tsx`، `manifest.webmanifest`، `tsconfig.app.json` (+types node للاختبارات)، `docs/DECISIONS.md` (**E-050**)، `docs/STATE.md` (§0.9).

**تعديل الباك إند الوحيد:** `backend/app/main.py` — إضافة `GZipMiddleware(minimum_size=1024)` لأن الخادم يقدّم الواجهة بنفسه (JS من 340 kB إلى 99 kB). لا تعديل على `state.py` أو العتبات أو V1–V5 أو أي منطق مطابقة.

**الهوية البصرية:** كحلي ليلي `#0B0F2A/#12183F` · بنفسجي `#6150EA` = دور الذكاء الاصطناعي · فيروزي `#2EF2C2` = دور المحرك/التحقق · ذهبي `#B48A2C` للإطارات والخطوط الشعرية فقط (لا على نص، لا كحالة) · Readex Pro للواجهة + Amiri Quran لنص المصدر. «لم يوجد» بلون رمادي-أردوازي محايد (E-032)، لا أحمر.

## 2. الخطوط الحمراء — كيف احتُرمت (لا تكسرها عند الدمج)
1. **لا نص ديني مكتوب باليد.** نص الرئيسية من حالات `eval/` (A-016، F-075) و`smoke` (CASES[1]، CASES[7])؛ كلمات المصدر شرائح من `source_text` في استجابة الـAPI. اختبار يتحقق من ذلك.
2. **نص القرآن لا يُشوَّه.** الحركة حول النص فقط (حلقة، إطار، خلفية تظليل). اختبار يمنع `transform/scale/skew` و`letter-spacing≠0` على عناصر النص.
3. **الحالات الأربع** تُقرأ من `messages/*.json` فقط؛ لا كلمات حكم (اختبار + ماسح الباك إند: 0 من 546 نصًا).
4. **لا أرقام مخترعة.** كل رقم في `/trust` من `trust.json`، واختبار يقرأ السطر المذكور ويتحقق أن الرقم فيه حرفيًا.
5. **ما لم يُبنَ لا يُعرض كأنه يعمل.** اختبار: الخدمات غير الحية لا تربط إلى `/check`، وأوضاع «قريبًا» لا تستدعي `/v1/check`.
6. **لا أسرار في الواجهة.** لا مفاتيح، ولا شيء من `docs/internal/` أو `.intake/` في الحزمة.

## 3. القياسات عند التسليم (أعد إنتاجها قبل أن تثق بها)
| | النتيجة |
|---|---|
| `tsc -b` | نظيف |
| vitest | **26/26** (13 جديدة) |
| ruff + mypy + pytest | أخضر |
| `scripts/check_site_lexicon.py` | 0/546 |
| axe WCAG 2.2 AA | **0** على 6 صفحات × فاتح/داكن |
| Lighthouse جوال (perf/a11y/BP/SEO) | `/` 92/100/100/100 · `/check` 98/100/100/100 · `/trust` 91/100/100/100 · CLS ≤ 0.004 (التقارير في `lighthouse/`) |
| تجاوب | 375/768/1440 بلا تمرير أفقي، صفر أخطاء console (اللقطات في `screenshots/after/`) |

## 4. خطوات الدمج (نفّذها بالترتيب)
```bash
# 0) نزّل الحزمة وفكّها
# الفرع منشور على GitHub: design/claude (Pull Request مفتوح) — لا حاجة لأي حزمة

# 1) في المستودع
cd /home/user/webapp            # أو مسار المستودع عندك
git fetch origin && git checkout main && git pull --ff-only
git fetch origin design/claude:design/claude
git log --oneline main..design/claude          # يجب أن ترى commitين: f005536, 54e24ff

# إن تقدّم main عن 817c6fb: أعد التأسيس وحلّ التعارضات لصالح main ما لم يكسر ذلك الواجهة
git checkout design/claude && git rebase origin/main

# 2) البوابات (كلها يجب أن تنجح)
bash scripts/bootstrap.sh && make smoke
make eval-full PY=backend/.venv/bin/python && git checkout eval/REPORT.md
backend/.venv/bin/python scripts/check_site_lexicon.py
backend/.venv/bin/python scripts/gen_trust.py && git diff --exit-code frontend/src/__generated__/trust.json
cd frontend && npm ci && npx tsc -b && npx oxlint && npx vitest run && npm run build && cd ..

# 3) تشغيل وتحقق يدوي + E2E
pm2 start ecosystem.config.cjs      # API :8000 يقدّم frontend/dist
# افتح / و /check و /trust على 375 و 1440؛ شغّل فحصًا حقيقيًا من «منشور فيه اقتباسات متعددة»

# 4) الدمج
git checkout main && git merge --no-ff design/claude -m "merge: UI v3 «البصيرة» (E-050)"
git push origin main
# 5) تحقّق ما بعد الدمج (CLAUDE.md): pull نظيف + كل البوابات مرة أخرى على main
```

## 5. ما بقي — نفّذه أنت بعد الدمج (كل بند بقياس + سطر في DECISIONS)
1. **E2E**: `frontend/e2e/check.spec.ts` كُتب للصفحة القديمة (يبدأ من `/` ويبحث عن `#text`). حدّثه: الفحص صار على `/check`، و`textarea#text` ما زال موجودًا، وزر «افحص» كما هو. أضف حالة للرئيسية (العدسة تضيء 4 اقتباسات، و`textContent` للمنشور = النص المسجّل).
2. **حجم JS**: 99.2 kB gz > حد 90 kB السابق. الحل المقترح: تحميل `SITE.en` + `messages/en.json` عند الطلب، ونقل `hero.json` لملف منفصل بـ`fetch`.
3. **تحديث `hero.json`** عند تغيّر المحرك: `backend/.venv/bin/python scripts/gen_examples.py --record http://localhost:8000` ثم تحقق أن الحالات الأربع ما زالت موجودة (الاختبار يفشل إن لا).
4. **README** و`docs/UX_LOG.md`: أضف قسم UI v3 بالأرقام المقاسة عندك.
5. **الخدمات «قريبًا»** (الإنجليزي، الحارس، MCP، إيصال التحقق): عند بناء أي منها، غيّر `live: true` في `frontend/src/site/services.ts` واحذف لوحة «قريبًا» في `Check.tsx` — **فقط بعد أن تعمل فعلًا على المحرك ولها اختبارات**.

## 6. ⚠️ تنبيه أمني يخص المستودع (افعله أولًا إن لم يُفعل)
مستودع `alabasi2025/Project-Basira` كان **عامًا** وفيه `docs/internal/` (12 ملفًا، منها مراجعات الملاحق). `CLAUDE.md` يمنع نشره. أبلغ المالك، واقترح جعل المستودع خاصًا، ثم نظّف التاريخ قبل التسليم العام (وفق §"Repository visibility & publication gate" في `CLAUDE.md`). **هذه الحزمة لا تحتوي أي ملف من `docs/internal/`.**

## 7. محتوى الحزمة
```
PROMPT_FOR_AGENT.md      هذا الملف
design-claude.bundle     git bundle (main..design/claude) — الطريقة المفضّلة
patches/0001,0002.patch  نفس الـcommitين بصيغة git am — بديل
files/                   نسخ كاملة من كل ملف تغيّر (للمراجعة دون git)
CHANGED_FILES.txt        قائمة الملفات · REFS.txt (main base, branch tip)
screenshots/before/      الواجهة القديمة · screenshots/after/  الجديدة على 375/768/1440 + تدفق فحص حقيقي
lighthouse/              تقارير Lighthouse JSON (جوال)
```
