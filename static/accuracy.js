// /accuracy page: measured accuracy and its limits. Needs common.js.
// Numbers: docs/accuracy.md, "다시 잰 결과 (2026-09-16)". Update both together.
const ACC_TEXT={};
ACC_TEXT.ko={
accTitle:'얼마나 맞히는지, 무엇을 못 하는지 그대로 적었습니다.',
accLead:'CADLens가 도면에서 무엇을 얼마나 잡는지 정답이 달린 도면으로 측정했습니다. 좋은 숫자만 고르지 않고 측정의 한계와 아직 못 잡는 것까지 함께 공개합니다.',
accDate:'2026-09-16 측정 · 규칙 검사만 측정했고 AI가 매기는 투상도 30점은 뺐습니다.',
accNumsT:'측정 결과',accDefsT:'숫자 읽는 법',accWeightT:'세 숫자의 무게는 다릅니다',accRealT:'실제 도면 측정의 한계',accAiT:'AI 점수는 확정 점수가 아닙니다',
accWeakT:'아직 못 잡는 것',accWeakD:'측정으로 드러났거나, 원리상 틀릴 수 있다고 알고 있는 부분입니다.',
accLogT:'측정하며 찾아 고친 것',accLogD:'숫자가 좋게 나오기 전에 먼저 틀린 것들입니다.',
accCtaT:'측정 도구와 기록은 모두 공개돼 있습니다',accCtaD:'python bench.py 로 누구나 같은 측정을 다시 할 수 있습니다.',accDocLink:'측정 기록 보기 (GitHub)',
tocT:'이 페이지에서',
nums:[
['실제 수험생 도면','23 / 23장','결함 63건 중 63건 검출 · 헛지적 0건','그림만 보고 정답을 달 수 있는 6개 항목만 쟀습니다. 한 학생의 연습 도면입니다.','가장 중요한 숫자'],
['합성 도면','100 / 100장','결함 99건 중 99건 검출 · 헛지적 0건','공개문제 형식을 본떠 코드로 만든 도면입니다.',''],
['기준 도면','28 / 28장','결함 27건 중 27건 검출 · 헛지적 0건','결함을 하나씩 심어 만든 회귀 시험용 도면입니다.','']],
defs:[
['검출률 (recall)','도면에 실제로 있는 결함 중 CADLens가 잡아낸 비율입니다. 낮으면 수험생이 놓친 것을 같이 놓칩니다.'],
['정확도 (precision)','CADLens가 지적한 것 중 실제 결함인 비율입니다. 낮으면 멀쩡한 도면을 틀렸다고 해서 헷갈리게 합니다.'],
['완전 일치','한 도면의 지적 목록이 정답과 정확히 같은 경우입니다. 부분 정답을 후하게 쳐주지 않으려고 함께 셉니다.']],
weight:['기준 도면과 합성 도면은 우리가 결함을 심어 만든 도면이라 100%가 나오는 것이 당연합니다. 우리 검사가 우리가 만든 결함을 잡는지, 멀쩡한 도면에 헛지적을 하지 않는지 확인하는 회귀 시험입니다.',
'실제 수험생 도면에서의 정확도를 보여 주는 숫자는 실제 도면 칸뿐입니다. 합성 도면에서는 멀쩡하다가 실제 도면에서 처음 드러난 문제도 있었습니다. 기하공차를 GDT 전용 글꼴로 찍은 도면을 읽지 못해, 실제 도면 9장이 전부 오작으로 나온 일이 그 예입니다.'],
real:['기계과 학생 한 명에게 받은 Inventor 도면 32장을 DXF로 내보내 30장을 얻었고, 같은 도면의 이전 저장본 7쌍을 빼서 서로 다른 도면 23장으로 셉니다.',
'정답은 도면을 그림으로 바꿔 눈으로 달았습니다. 수험생 본인이나 선생님이 채점한 것이 아닙니다.',
'그림만 보고 확실히 가릴 수 있는 6개 항목만 쟀습니다 — 표면거칠기 기호, 기하공차, 치수, 주서, 표제란·윤곽선, 중심선. 치수 없는 구멍처럼 개수를 세야 하는 항목은 정답을 달 수 없어 뺐습니다.',
'23장 중 20장이 표면거칠기 기호도 기하공차도 없는 작업 중간 상태였고, 23장 모두 주서가 없었습니다. 그래서 주로 “없는 것을 없다고 하는가”를 확인했고, “있는 것을 있다고 보는가”는 기호가 들어 있는 3장에서만 확인했습니다.',
'여러 학생의 완성 도면으로 다시 재야 합니다.'],
ai:['같은 도면을 여러 번 채점하면 투상도 점수가 달라집니다. 2026-08-22에 예제 도면을 5번씩 채점했을 때 무엇을 지적하는지는 같았지만 감점 폭이 흔들렸고, 가장 크게는 한 도면에서 0점부터 18점까지 벌어졌습니다.',
'그 표본은 기계 부품이 아닌 무늬 도면이었고, 측정 당시에는 AI에게 도면 일부만 보내던 문제(2026-09-11에 고침)도 있었습니다. 실제 수험생 도면으로 다시 재야 합니다. 그래서 화면에서 AI가 매긴 항목에는 AI 표시를 붙이고, 확정 채점이 아니라고 안내합니다.'],
weak:[
['선으로만 그린 표면거칠기 기호','기호에 √ · Ra 값 · 다듬질 기호 같은 문자가 없으면 못 봐서, 실격으로 잘못 판정할 수 있습니다.'],
['선과 문자로 직접 그린 기하공차 기입틀','CAD의 공차 기입 기능이나 GDT 문자로 넣지 않으면 못 봐서, 실격으로 잘못 판정할 수 있습니다.'],
['중심선','레이어·선종류 이름(CENTER, 중심, DASHDOT 계열)으로 찾기 때문에 이름이 다르면 못 봅니다.'],
['선 굵기','레이어에 적힌 값으로 봅니다. 요소마다 따로 준 굵기는 다를 수 있고, 색으로 굵기를 내는 도면은 판정하지 않습니다.'],
['척도 · 각법 오류','합성 도면으로는 이 결함을 만들 수 없어 실제 도면으로만 검증할 수 있습니다.'],
['투상도 개수와 배치','뷰 경계를 알 수 없는 DXF는 개수 검사를 건너뜁니다. 부품의 균형 배치는 규칙으로 판정하지 않습니다.'],
['치수 없는 구멍','실제 도면 30장에서 헛지적이 22장에서 10장으로 줄었지만, 남은 10장을 모두 눈으로 확인하지는 않았습니다.']],
log:[
['2026-08-22','AI가 백지를 채점하고 있었습니다','도면 단위가 미터·인치인 도면을 밀리미터로 보지 않아 AI에게 빈 그림이 갔습니다. 단위를 환산해 그리도록 고쳤습니다.'],
['2026-08-30','합성 도면 100장 중 처음엔 66장만 일치했습니다','나머지는 정답을 잘못 적은 것과 검사가 도면을 잘못 읽은 것이었습니다. 제3각법 기호의 원을 구멍으로, 뷰 이름표를 주서로, 부품 외형을 윤곽선으로 보던 세 가지를 고쳤습니다.'],
['2026-09-06','실제 도면 9장이 전부 오작으로 나왔습니다','GDT 전용 글꼴로 찍은 기하공차를 읽지 못해서였습니다. 고친 뒤 기하공차가 들어 있던 2장은 오작에서 벗어났습니다.'],
['2026-09-11','AI가 A2 도면의 절반만 보고 채점했습니다','그림을 자르지 않고 해상도를 낮추도록 고쳤습니다. 뷰 이름표와 비교표 빈 칸을 주서로 세던 것도 함께 고쳤습니다.'],
['2026-09-12','제도 기본에 어긋난 검사를 고쳤습니다','치수는 한 곳에만 적는다, 윤곽선 밖은 채점하지 않는다, 나사는 호칭으로 적는다, 원호는 구멍이 아니다. 치수 없는 구멍 헛지적이 22장에서 10장으로 줄었습니다.'],
['2026-09-16','합성 도면 정답 파일이 옛 규칙에 머물러 있었습니다','일반공차 규칙을 KS에 맞춰 바꾼 뒤 정답 파일을 안 고쳐, 다시 재면 검출률이 94.3%로 나왔습니다. 정답 파일을 고치고 다시 쟀습니다.']]
};
ACC_TEXT.en={
accTitle:'How accurate it is, and what it still misses.',
accLead:'We measured what CADLens catches on drawings with known answers. We publish the limits of the measurement and what it still cannot catch, not just the good numbers.',
accDate:'Measured 2026-09-16 · rule-based checks only; the 30 AI-graded points for views are excluded.',
accNumsT:'Results',accDefsT:'How to read the numbers',accWeightT:'The three numbers do not weigh the same',accRealT:'Limits of the real-drawing measurement',accAiT:'The AI score is not final',
accWeakT:'What it still misses',accWeakD:'Weak spots found by measuring, or known to be wrong in principle.',
accLogT:'What measuring made us fix',accLogD:'Things that were wrong before the numbers looked good.',
accCtaT:'The measurement tools and records are public',accCtaD:'Anyone can rerun the same measurement with python bench.py.',accDocLink:'See the measurement log (GitHub, Korean)',
tocT:'On this page',
nums:[
['Real exam drawings','23 / 23','Caught 63 of 63 defects · 0 false alarms','Only the 6 items that can be labeled by eye were measured. All drawings are one student\'s practice work.','The number that matters'],
['Synthetic drawings','100 / 100','Caught 99 of 99 defects · 0 false alarms','Drawings generated in code, modeled on the public exam format.',''],
['Reference drawings','28 / 28','Caught 27 of 27 defects · 0 false alarms','Regression drawings with one defect planted in each.','']],
defs:[
['Recall','The share of real defects in a drawing that CADLens catches. When it is low, CADLens misses what the candidate missed.'],
['Precision','The share of CADLens findings that are real defects. When it is low, sound drawings get flagged and confuse the candidate.'],
['Exact match','The findings for a drawing are exactly the answer set. Counted so that partly right answers get no extra credit.']],
weight:['Reference and synthetic drawings have defects we planted ourselves, so 100% is expected. They are regression tests: do our checks catch the defects we made, and stay quiet on sound drawings?',
'Only the real-drawing column says how CADLens does on actual exam drawings. Some problems never showed up on synthetic drawings and appeared only on real ones — for example, geometric tolerances typed with a dedicated GDT font could not be read, so all 9 real drawings came out disqualified.'],
real:['We received 32 Inventor drawings from one mechanical engineering student, exported them to 30 DXF files, and count 23 distinct drawings after removing 7 older saves of the same drawing.',
'Answers were labeled by eye from rendered images, not graded by the student or a teacher.',
'Only 6 items that can be decided from the image alone were measured — surface finish symbols, geometric tolerances, dimensions, notes, title block and border, center lines. Items that need counting, such as holes without dimensions, could not be labeled and were left out.',
'20 of the 23 drawings were unfinished, with no finish symbols or geometric tolerances, and none of the 23 had notes. So this mostly tests "does it say missing when it is missing"; "does it see what is there" was confirmed on only 3 drawings.',
'It needs to be measured again on finished drawings from many students.'],
ai:['Grading the same drawing several times gives different view scores. When each sample drawing was graded 5 times on 2026-08-22, the findings stayed the same but the deductions varied — on one drawing from 0 to 18 points.',
'That sample was a pattern drawing rather than a machine part, and at the time only part of the drawing was sent to the AI (fixed 2026-09-11). It needs to be measured again on real exam drawings. That is why AI-graded items carry an AI badge and are labeled as not final.'],
weak:[
['Finish symbols drawn only with lines','Without text such as √, an Ra value or a finish letter, they are not seen and the drawing can be wrongly disqualified.'],
['Feature control frames drawn with lines and text','Unless added with the CAD tolerance tool or GDT characters, they are not seen and the drawing can be wrongly disqualified.'],
['Center lines','Found by layer or linetype names (CENTER, 중심, DASHDOT and similar), so other names are missed.'],
['Line widths','Read from layer settings. Widths set per object may differ, and drawings that set widths by color are not judged.'],
['Scale and projection errors','These defects cannot be made in synthetic drawings, so they can only be verified on real ones.'],
['Number and layout of views','Skipped for DXF files whose view boundaries cannot be read. Balanced layout is not judged by rules.'],
['Holes without dimensions','False alarms on 30 real drawings dropped from 22 to 10 drawings, but the remaining 10 have not all been checked by eye.']],
log:[
['2026-08-22','The AI was grading blank images','Drawings in meters or inches were not converted to millimeters, so the AI received an empty picture. Units are now converted before rendering.'],
['2026-08-30','Only 66 of 100 synthetic drawings matched at first','The rest were wrong answers in the label file and drawings the checks misread. We fixed three misreadings: the third-angle symbol read as holes, view labels read as notes, and a part outline read as the border.'],
['2026-09-06','All 9 real drawings came out disqualified','Geometric tolerances typed in a dedicated GDT font could not be read. After the fix, the 2 drawings that had them were no longer disqualified.'],
['2026-09-11','The AI saw only half of an A2 drawing','Images are no longer cropped; the resolution is lowered instead. View labels and empty comparison-table cells were also being counted as notes, and that was fixed too.'],
['2026-09-12','Checks that broke drafting basics were fixed','Each dimension is given only once; nothing outside the border is graded; threads are given by designation; arcs are not holes. False alarms for holes without dimensions dropped from 22 to 10 drawings.'],
['2026-09-16','The synthetic answer file still followed an old rule','After the general-tolerance rule was aligned with KS, the answer file was not updated, so a rerun showed 94.3% recall. The answers were corrected and measured again.']]
};
ACC_TEXT.ja={
accTitle:'どれだけ当たるか、何ができないかをそのまま書きました。',
accLead:'CADLens が図面から何をどれだけ見つけるかを、正解付きの図面で測定しました。良い数字だけを選ばず、測定の限界とまだ見つけられないものも公開します。',
accDate:'2026-09-16 測定 · ルール検査のみを測定し、AI が採点する投影図 30 点は除外しました。',
accNumsT:'測定結果',accDefsT:'数字の読み方',accWeightT:'三つの数字の重みは違います',accRealT:'実図面測定の限界',accAiT:'AI の点数は確定した点数ではありません',
accWeakT:'まだ見つけられないもの',accWeakD:'測定で分かったもの、または原理的に誤りうると分かっている部分です。',
accLogT:'測定しながら見つけて直したこと',accLogD:'数字が良くなる前に、まず間違っていたことです。',
accCtaT:'測定ツールと記録はすべて公開しています',accCtaD:'python bench.py で誰でも同じ測定をやり直せます。',accDocLink:'測定記録を見る（GitHub・韓国語）',
tocT:'このページの内容',
nums:[
['実際の受験者図面','23 / 23 枚','欠陥 63 件中 63 件を検出 · 誤指摘 0 件','画像だけで正解を付けられる 6 項目のみ測定しました。一人の学生の練習図面です。','最も重要な数字'],
['合成図面','100 / 100 枚','欠陥 99 件中 99 件を検出 · 誤指摘 0 件','公開問題の形式をまねてコードで作った図面です。',''],
['基準図面','28 / 28 枚','欠陥 27 件中 27 件を検出 · 誤指摘 0 件','欠陥を一つずつ仕込んだ回帰テスト用の図面です。','']],
defs:[
['検出率 (recall)','図面に実際にある欠陥のうち、CADLens が見つけた割合です。低いと受験者の見落としを一緒に見落とします。'],
['適合率 (precision)','CADLens が指摘したもののうち、実際の欠陥である割合です。低いと問題のない図面を誤りとして混乱させます。'],
['完全一致','一枚の図面の指摘リストが正解と完全に同じ場合です。部分的な正解を甘く数えないために一緒に数えます。']],
weight:['基準図面と合成図面は私たちが欠陥を仕込んで作った図面なので、100% になるのは当然です。私たちの検査が自分で作った欠陥を見つけるか、問題のない図面に誤指摘しないかを確かめる回帰テストです。',
'実際の受験者図面での精度を示す数字は、実図面の欄だけです。合成図面では問題なく、実図面で初めて現れた問題もありました。GDT 専用フォントで入力した幾何公差を読めず、実図面 9 枚がすべて失格と判定されたのがその例です。'],
real:['機械科の学生一人から受け取った Inventor 図面 32 枚を DXF に書き出して 30 枚を得て、同じ図面の以前の保存版 7 組を除き、異なる図面 23 枚として数えます。',
'正解は図面を画像にして目視で付けました。受験者本人や先生が採点したものではありません。',
'画像だけで確実に判断できる 6 項目のみ測定しました — 表面粗さ記号、幾何公差、寸法、注記、表題欄・輪郭線、中心線。寸法のない穴のように数を数える必要がある項目は、正解を付けられないため除きました。',
'23 枚中 20 枚は表面粗さ記号も幾何公差もない作業途中の状態で、23 枚すべてに注記がありませんでした。そのため主に「ないものをないと言えるか」を確かめており、「あるものをあると見られるか」は記号が入った 3 枚でしか確認していません。',
'複数の学生の完成図面で測り直す必要があります。'],
ai:['同じ図面を何度も採点すると投影図の点数が変わります。2026-08-22 にサンプル図面をそれぞれ 5 回採点したところ、指摘内容は同じでしたが減点幅がぶれ、最も大きいものでは一枚の図面で 0 点から 18 点まで開きました。',
'その標本は機械部品ではなく模様の図面で、当時は AI に図面の一部しか送っていない問題（2026-09-11 に修正）もありました。実際の受験者図面で測り直す必要があります。そのため画面では AI が採点した項目に AI 表示を付け、確定した採点ではないと案内しています。'],
weak:[
['線だけで描いた表面粗さ記号','記号に √ · Ra 値 · 仕上げ記号などの文字がないと認識できず、誤って失格と判定することがあります。'],
['線と文字で直接描いた幾何公差の記入枠','CAD の公差記入機能や GDT 文字で入れないと認識できず、誤って失格と判定することがあります。'],
['中心線','画層・線種の名前（CENTER、중심、DASHDOT 系）で探すため、名前が違うと見つけられません。'],
['線の太さ','画層に設定された値で判断します。要素ごとに付けた太さは異なることがあり、色で太さを出す図面は判定しません。'],
['尺度 · 投影法の誤り','合成図面ではこの欠陥を作れないため、実図面でしか検証できません。'],
['投影図の数と配置','ビューの境界が読めない DXF では数の検査を省略します。部品のバランスのよい配置はルールで判定しません。'],
['寸法のない穴','実図面 30 枚での誤指摘は 22 枚から 10 枚に減りましたが、残り 10 枚をすべて目視で確認したわけではありません。']],
log:[
['2026-08-22','AI が白紙を採点していました','単位がメートル・インチの図面をミリメートルとして扱わず、AI に空の画像が送られていました。単位を換算して描くように直しました。'],
['2026-08-30','合成図面 100 枚のうち最初は 66 枚しか一致しませんでした','残りは正解の書き間違いと、検査による図面の読み違いでした。第三角法記号の円を穴として、ビュー名を注記として、部品の外形を輪郭線として見ていた三つを直しました。'],
['2026-09-06','実図面 9 枚がすべて失格と出ました','GDT 専用フォントで入力した幾何公差を読めなかったためです。修正後、幾何公差が入っていた 2 枚は失格ではなくなりました。'],
['2026-09-11','AI が A2 図面の半分だけを見て採点していました','画像を切り取らず解像度を下げるように直しました。ビュー名や比較表の空欄を注記として数えていた点も直しました。'],
['2026-09-12','製図の基本に反する検査を直しました','寸法は一か所だけに記入する、輪郭線の外は採点しない、ねじは呼びで記入する、円弧は穴ではない。寸法のない穴の誤指摘が 22 枚から 10 枚に減りました。'],
['2026-09-16','合成図面の正解ファイルが古い規則のままでした','普通公差の規則を KS に合わせて変えた後に正解ファイルを直しておらず、測り直すと検出率が 94.3% と出ました。正解ファイルを直して測り直しました。']]
};
ACC_TEXT.zh={
accTitle:'能查准多少、还有什么查不出，都如实写在这里。',
accLead:'我们用带有标准答案的图纸测量了 CADLens 能从图纸中查出什么、查出多少。不只挑好看的数字，测量的局限和目前还查不出的问题也一并公开。',
accDate:'2026-09-16 测量 · 只测量规则检查，不含由 AI 评分的视图 30 分。',
accNumsT:'测量结果',accDefsT:'如何理解这些数字',accWeightT:'三个数字的分量不同',accRealT:'真实图纸测量的局限',accAiT:'AI 分数不是最终分数',
accWeakT:'目前还查不出的问题',accWeakD:'通过测量发现的，或已知原理上可能出错的部分。',
accLogT:'测量过程中发现并修正的问题',accLogD:'在数字变好之前，先暴露出来的错误。',
accCtaT:'测量工具和记录全部公开',accCtaD:'任何人都可以用 python bench.py 重新进行同样的测量。',accDocLink:'查看测量记录（GitHub · 韩语）',
tocT:'本页内容',
nums:[
['真实考生图纸','23 / 23 张','63 处缺陷全部查出 · 误报 0 处','只测量了凭图像就能标注答案的 6 个项目。全部是同一名学生的练习图纸。','最重要的数字'],
['合成图纸','100 / 100 张','99 处缺陷全部查出 · 误报 0 处','仿照公开试题格式用代码生成的图纸。',''],
['基准图纸','28 / 28 张','27 处缺陷全部查出 · 误报 0 处','每张植入一个缺陷的回归测试用图纸。','']],
defs:[
['检出率 (recall)','图纸中实际存在的缺陷里，被 CADLens 查出的比例。偏低时，考生漏掉的问题它也会一起漏掉。'],
['精确率 (precision)','CADLens 指出的问题里，确实是缺陷的比例。偏低时，会把没问题的图纸判为有误，让考生困惑。'],
['完全一致','一张图纸的问题列表与答案完全相同。为了不对部分正确放宽计分，一并统计。']],
weight:['基准图纸和合成图纸是我们自己植入缺陷制作的，得到 100% 是理所当然的。它们是回归测试：检查我们的规则能否查出自己制造的缺陷，并且不会对没问题的图纸误报。',
'能反映真实考生图纸准确度的，只有真实图纸那一栏。有些问题在合成图纸上完全没有出现，直到真实图纸才第一次暴露。例如无法读取用 GDT 专用字体输入的几何公差，导致 9 张真实图纸全部被判为失格。'],
real:['从一名机械专业学生那里收到 32 张 Inventor 图纸，导出为 DXF 后得到 30 张；去掉同一图纸的 7 组旧存档后，按 23 张不同的图纸计算。',
'答案是把图纸渲染成图片后用肉眼标注的，不是考生本人或老师评分的。',
'只测量了凭图像就能确定的 6 个项目 — 表面粗糙度符号、几何公差、尺寸、技术要求、标题栏与图框、中心线。像缺少尺寸的孔这类需要计数的项目无法标注答案，因此没有纳入。',
'23 张中有 20 张是既没有粗糙度符号也没有几何公差的半成品，23 张全都没有技术要求。因此主要验证的是“没有的能否判为没有”，“有的能否识别出来”只在含有符号的 3 张上得到确认。',
'需要用多名学生的完成图纸重新测量。'],
ai:['同一张图纸多次评分，视图分数会不同。2026-08-22 将示例图纸各评分 5 次时，指出的问题相同，但扣分幅度不稳定，差距最大的一张图纸从 0 分到 18 分不等。',
'那份样本是花纹图案而不是机械零件，而且当时还存在只把图纸的一部分发给 AI 的问题（已于 2026-09-11 修正）。需要用真实考生图纸重新测量。因此页面上由 AI 评分的项目都带有 AI 标记，并说明不是最终评分。'],
weak:[
['只用线条画出的表面粗糙度符号','符号中没有 √ · Ra 值 · 加工符号之类的文字时无法识别，可能被误判为失格。'],
['用线条和文字直接画出的几何公差框格','不是用 CAD 的公差标注功能或 GDT 字符输入时无法识别，可能被误判为失格。'],
['中心线','按图层或线型名称（CENTER、중심、DASHDOT 系列）查找，名称不同就找不到。'],
['线宽','按图层中设置的数值判断。逐个对象单独设置的线宽可能不同，用颜色控制线宽的图纸不作判定。'],
['比例 · 投影法错误','合成图纸无法制造这类缺陷，只能用真实图纸验证。'],
['视图数量与布局','无法读出视图边界的 DXF 会跳过数量检查。零件的均衡布局不用规则判定。'],
['缺少尺寸的孔','在 30 张真实图纸上的误报从 22 张减少到 10 张，但剩下的 10 张并没有全部用肉眼确认。']],
log:[
['2026-08-22','AI 一直在给空白图片评分','单位为米或英寸的图纸没有换算成毫米，发给 AI 的是一张空白图片。现在会先换算单位再绘制。'],
['2026-08-30','100 张合成图纸起初只有 66 张一致','其余是答案写错，以及检查读错了图纸。我们修正了三处误读：把第三角法符号的圆当成孔、把视图名称当成技术要求、把零件外形当成图框。'],
['2026-09-06','9 张真实图纸全部被判为失格','原因是无法读取用 GDT 专用字体输入的几何公差。修正后，含有几何公差的 2 张不再被判为失格。'],
['2026-09-11','AI 只看了 A2 图纸的一半就评分','改为不裁剪图片、改用降低分辨率的方式。把视图名称和对照表空格当成技术要求的问题也一并修正。'],
['2026-09-12','修正了违背制图基础的检查','同一尺寸只标注一次；图框外不评分；螺纹按代号标注；圆弧不是孔。缺少尺寸的孔的误报从 22 张减少到 10 张。'],
['2026-09-16','合成图纸的答案文件还停留在旧规则','按 KS 调整未注公差规则后没有更新答案文件，重新测量时检出率只有 94.3%。修正答案文件后重新测量。']]
};

const ACC_LISTS=['tocT','nums','defs','weight','real','ai','weak','log'];
for(const l in ACC_TEXT)Object.assign(I18N[l],Object.fromEntries(Object.entries(ACC_TEXT[l]).filter(([k])=>!ACC_LISTS.includes(k))));
const ACC_SECTIONS=[['results','accNumsT'],['read','accDefsT'],['weight','accWeightT'],['real','accRealT'],['ai','accAiT'],['weak','accWeakT'],['log','accLogT']];

function drawAcc(){
  const T=ACC_TEXT[lang]||ACC_TEXT.ko;
  document.title=`${t('navAcc')} · CADLens`;
  $('#nums').innerHTML=T.nums.map(([k,big,sub,note,badge])=>`<div class="num${badge?' hl':''}"><span class="k">${esc(k)}${badge?`<span class="badge">${esc(badge)}</span>`:''}</span><b>${esc(big)}</b><p>${esc(sub)}</p><small>${esc(note)}</small></div>`).join('');
  $('#defs').innerHTML=T.defs.map(([h,d])=>`<div class="def"><b>${esc(h)}</b><p>${esc(d)}</p></div>`).join('');
  $('#weightText').innerHTML=T.weight.map(p=>`<p>${esc(p)}</p>`).join('');
  $('#realList').innerHTML=T.real.map(x=>`<li>${esc(x)}</li>`).join('');
  $('#aiText').innerHTML=T.ai.map(p=>`<p>${esc(p)}</p>`).join('');
  $('#weakList').innerHTML=T.weak.map(([h,d])=>`<div><b>${esc(h)}</b><p>${esc(d)}</p></div>`).join('');
  $('#logList').innerHTML=T.log.map(([d,h,p])=>`<li><time datetime="${d}">${d}</time><b>${esc(h)}</b><p>${esc(p)}</p></li>`).join('');
  $('#toc').innerHTML=`<b>${esc(T.tocT)}</b>`+ACC_SECTIONS.map(([id,k])=>`<a href="#${id}">${esc(t(k))}</a>`).join('');
}
onLang.push(drawAcc);
applyLang();
reveal();
