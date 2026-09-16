// Home page: upload, results, guide. Needs common.js.
const kb=n=>n>=1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
const FINDING_I18N={
en:{DQ_NO_SURFACE_SYMBOL:['Disqualified: no surface finish symbols','The part drawing has no surface finish symbol at all. Under the published grading criteria, a part drawing without surface finish symbols is disqualified.','Add a symbol to every machined face (Annotate > Surface Texture Symbol), and define the finish grades (w/x/y or Ra values) in the notes.'],DQ_NO_GEOMETRIC_TOL:['Disqualified: no geometric tolerance symbols','The part drawing has no geometric tolerance frame at all. A part drawing without geometric tolerances is disqualified.','Assign datums (A, B, ...) first, then add concentricity, perpendicularity, parallelism and similar controls (Annotate > Geometric Tolerance).'],DQ_PROJECTION:['Disqualified: first-angle projection used','Third-angle projection is required but the drawing uses first-angle. A drawing whose projection method does not match the requirement is disqualified.','Switch to third-angle in Manage > Style Editor > Drafting Standard, and check the projection symbol in the title block.'],DQ_SHEET_SIZE:['Disqualified: sheet size does not match','The sheet is not the required size. A drawing not made on the required sheet size is disqualified.','Right-click the sheet > Edit Sheet and set the required size.'],DQ_SCALE:['Disqualification risk: non-standard scale','This scale is not one of the KS standard scales.','Change the view scale to a standard value such as 1:1, 1:2, or 2:1.'],EX_NO_DIMS:['No dimensions at all','The drawing has no dimensions. All 15 points for dimensioning are lost.','Add the principal dimensions with Annotate > Dimension.'],EX_DIM_MISSING:['Possible missing dimensions in {n} place(s)','There are circles or holes with no dimension attached. Missing dimensions are a direct deduction.','Add a dimension to each. When several holes share a size, group them once, e.g. 4-Ø6.'],EX_TOL_FEW:['Too few toleranced dimensions','The share of dimensions carrying a tolerance is low. Functional dimensions need tolerances.','Start with the dimensions involved in assembly and fits.'],EX_SURFACE_EMPTY:['{n} surface finish symbol(s) with no value','Some surface finish symbols carry no value. A symbol without a value does not define a machining requirement.','Double-click each symbol and enter a value, e.g. w/x/y or Ra 1.6, Ra 6.3.'],EX_SURFACE_UNIFORM:['Only one surface finish value used','Every face carries the same roughness. Fitting faces and bearing seats must be distinguished from general machined faces.','Differentiate by function, e.g. y for fitting faces, x for general machining, no-machining for as-cast faces.'],EX_SURFACE_FEW:['Only {n} surface finish symbol(s)','There are few symbols relative to the machined faces. Each functional face should carry one.','Annotate fitting faces, bearing seats and sliding faces individually.'],EX_FCF_NO_DATUM:['No datum in any geometric tolerance','Every geometric tolerance frame has an empty datum reference. Perpendicularity, parallelism, concentricity, position and run-out are meaningless without a datum.','Assign a datum (A, B, ...) to the main axis or face, then enter it in the datum compartment of the frame.'],EX_FCF_NO_VALUE:['{n} geometric tolerance(s) with no value','The frame has a symbol but no tolerance value.','Double-click the frame and enter the tolerance value, e.g. 0.011.'],EX_FCF_FEW:['Only {n} geometric tolerance(s)','Two or more controls are usually expected against a datum, such as concentricity, perpendicularity or parallelism.','Add controls such as concentricity to datum A, or perpendicularity of the end face.'],EX_NO_NOTES:['No general notes','The drawing has no general notes. Omitting general tolerance, chamfer, heat treatment and surface treatment costs points.','For example: 1. General tolerance - a) machined: KS B ISO 2768-m ...'],EX_NOTE_ITEM:['A required item is missing from the notes','A required statement could not be found in the general notes.','Complete the notes with the missing item, such as the general tolerance, the finish grades, or the chamfer and fillet rule.'],EX_NO_TITLEBLOCK:['No title block or drawing format','No title block or drawing format (border and centre marks) could be found.','Right-click the sheet > Insert Title Block, and place the border and centre marks.'],EX_NO_HEAT:['No heat or surface treatment instruction','The notes carry no heat treatment or surface treatment instruction. Parts such as shafts and gears can lose points under Material and Treatment.','Add an instruction such as “overall heat treatment HRC 50±0.2”, and put the material code (SM45C, SCM415, GC200) in the parts list.'],EX_FEW_VIEWS:['Only {n} view(s)','There seem to be too few views to describe the shape of the part.','Lay out the top and side views from the front view, adding section and detail views where needed.'],EX_NO_CENTERLINE:['No centrelines or centre marks','Circles and holes have no centreline or centre mark. This violates the KS drafting standard.','Add them to every circle and symmetric feature with Annotate > Centreline / Centre Mark.'],EX_VIEW_NO_LABEL:['View has no identifying label','A section or detail view must carry a letter (A, B, ...) and its scale so the reader can tell which part it shows.','Right-click the view > Edit and turn on the label and scale display.'],EX_VIEW_NO_SCALE:['Enlarged or reduced view without a scale note','A view whose scale differs from the sheet scale must state that scale next to it.','Turn on the scale display in the view settings.'],EX_SHEET_SIZE:['Drawing area is not the required size','The public exam requires drawing on A2; A3 is the printing size. Your session\'s instructions take precedence.','Set the sheet to A2 (594x420 mm) and print on A3.'],EX_NO_PROJECTION_MARK:['No projection-method note','No \'third angle\' note or projection symbol was found in the title block. The projection method is a required entry.','Write the third-angle note in the title block and add the projection symbol.'],EX_NO_SHEET_SCALE:['No scale in the title block','The scale field of the title block could not be found. Scale is a required title-block entry.','Write 1:1 in the scale field (NS on the 3D isometric drawing).'],EX_SCALE_NOT_ONE:['Part drawing scale is not 1:1','The public exam requires part drawings at scale 1:1.','Set the title block and the view scales to 1:1.'],EX_VIEW_SCALE_MIXED:['{n} view(s) are not at 1:1','Part drawings are required at 1:1. Leave it as it is if the view is deliberately enlarged as a detail view.','Check the view scale and set it back to 1:1 unless it is a detail view.'],EX_NO_MATERIAL:['No material code','No material code (SM45C, SCM415, GC250 and the like) was found in the title block or parts list. Material entry is scored under Material and Treatment.','Write the KS material code for every part in the material column of the parts list.'],EX_NO_MASS:['No mass in the isometric parts list','A 3D rendered isometric drawing must carry each part mass in grams, rounded to one decimal, in the remarks column.','In Inventor set the material under File > iProperties > Physical, press Update, and copy the mass into the remarks column.'],EX_RULE_ERROR:['Check rule error','A rule could not be completed for this drawing.','Please report this result for review.'],DQ_NO_FIT:['Disqualified: no fit tolerance symbols','There is no fit symbol such as H7, js5 or h6. A part drawing without fit tolerance symbols is disqualified.','Add fit symbols to mating dimensions, e.g. bearing shaft Ø17js5, cover bore Ø47H7.'],EX_NO_ROUGH_TABLE:['No surface finish comparison table','You placed {n} surface finish symbol(s) but no comparison table defining the finish grades was found. Without it, no one can tell which roughness w, x and y stand for.','Put a √(√w, √x, √y) comparison table in the empty space above the drawing and define the finish grades in the notes.'],EX_NO_SPEC_TABLE:['No gear or spring data table','The parts list has a gear or spring, but no data table was found. Gears and springs cannot be made from shape dimensions alone, so values such as number of teeth, module and pressure angle must be listed in a data table.','Draw a data table in an empty area and fill in the tooth profile, module, pressure angle, number of teeth, pitch diameter, finishing method and accuracy.'],EX_LINEWEIGHT_NONE:['No line widths set on layers','No layer has a line width, and there is no sign of widths assigned by color. Printed as is, outlines and dimension lines come out the same width.','In layer properties set border 0.7, outline 0.5, hidden 0.35, center and dimension 0.25, and hatch 0.18 mm. If widths come from colors, check the plot pen settings.'],EX_LINEWEIGHT_FLAT:['Outline and thin lines differ too little in width ({n}×)','KS drafting standards require thin : thick lines of at least 1 : 2. If line widths are not distinguished, the drawing is hard to read and points are deducted.','Set outlines to 0.5 mm and dimension and center lines to 0.25 mm — exactly double.'],EX_TEXT_SIZE:['Dimension text height is {n} mm','KS text heights are chosen from set nominal sizes (2.24 · 2.5 · 3.15 · 3.5 · 4.5 · 5 · 6.3 · 7 · 9 · 10 mm), and 2.5 mm is the minimum. Dimension text in exam drawings is usually 3.15 or 3.5 mm.','Change the text height to 3.15 or 3.5 mm in the dimension style editor.'],EX_LAYOUT_FIRST_ANGLE:['Views look like first-angle placement','Views aligned with the front view appear only on the first-angle sides. In third-angle projection the top view goes above and the right-side view to the right. A projection method different from the requirement is disqualifying.','Place the top view above the front view and the right-side view to its right. If you only used bottom and left-side views, you can leave it as is.']},
ja:{DQ_NO_SURFACE_SYMBOL:['失格: 表面粗さ記号なし','部品図に表面粗さ記号が一つもありません。公開された採点基準では、表面粗さ記号を部品図に記入していない図面は失格です。','注釈 > 表面性状記号 で加工面ごとに記号を記入し、注記に仕上げ区分（w/x/y または Ra 値）を定義してください。'],DQ_NO_GEOMETRIC_TOL:['失格: 幾何公差記号なし','部品図に幾何公差の記入枠が一つもありません。幾何公差を記入していない部品図は失格です。','先にデータム（A、B…）を指定し、同軸度・直角度・平行度などを記入してください。'],DQ_PROJECTION:['失格: 第一角法で作図','要求される投影法は第三角法ですが、図面は第一角法です。投影法が要求と一致しない図面は失格です。','管理 > スタイル エディタ > 製図標準 で第三角法に変更し、表題欄の投影法記号も確認してください。'],DQ_SHEET_SIZE:['失格: 図面サイズ不一致','要求されたシートサイズではありません。要求された図面サイズで作図されていない作品は失格です。','シートを右クリック > シートの編集 で要求サイズに変更してください。'],DQ_SCALE:['失格の恐れ: 非標準の尺度','この尺度は KS の標準尺度ではありません。','ビューの尺度を 1:1、1:2、2:1 などの標準値に変更してください。'],EX_NO_DIMS:['寸法が一つもない','図面に寸法が全く記入されていません。寸法記入の 15 点をすべて失います。','注釈 > 寸法 で主要寸法を記入してください。'],EX_DIM_MISSING:['寸法漏れの疑い {n} 箇所','寸法が付いていない円・穴があります。寸法漏れは直接の減点対象です。','該当形状に寸法を追加してください。同じ大きさの穴が複数あれば「4-Ø6」のようにまとめて一度だけ記入します。'],EX_TOL_FEW:['公差指定寸法が少ない','公差が指定された寸法の割合が低いです。機能寸法には公差が必要です。','組立・はめあいに関わる寸法から公差を指定してください。'],EX_SURFACE_EMPTY:['値が空の表面粗さ記号 {n} 個','表面粗さ記号に値が入っていないものがあります。記号だけで値がなければ加工指示として成立しません。','記号をダブルクリックして値を入力してください。例）w/x/y または Ra 1.6、Ra 6.3'],EX_SURFACE_UNIFORM:['粗さの値が一種類のみ','すべての面に同じ粗さが指定されています。はめあい面・軸受接触面と一般加工面は仕上げ程度を区別する必要があります。','機能に応じて分けてください。例）はめあい面 y、一般加工面 x、黒皮面は除去加工不可。'],EX_SURFACE_FEW:['表面粗さ記号が {n} 個のみ','加工面に対して記号の数が少ないです。機能面ごとに記入されるべきです。','はめあい面・軸受接触面・すべり面にそれぞれ記入してください。'],EX_FCF_NO_DATUM:['幾何公差にデータムが一つもない','幾何公差の記入枠がすべてデータム参照が空です。直角度・平行度・同軸度・位置度・振れはデータムなしでは意味を成しません。','主要な軸や面にデータム（A、B…）を指定し、記入枠のデータム欄に入れてください。'],EX_FCF_NO_VALUE:['公差値が空の幾何公差 {n} 個','記号だけで公差値がありません。','記入枠をダブルクリックして公差値を入力してください。例）0.011'],EX_FCF_FEW:['幾何公差が {n} 個のみ','通常はデータム基準で同軸度・直角度・平行度など 2 つ以上が求められます。','データム A 基準の同軸度、端面の直角度などを追加してください。'],EX_NO_NOTES:['注記がない','注記（一般注記）がありません。普通公差・面取り・熱処理・表面処理を明示しないと減点されます。','例）1. 普通公差 - a) 加工部: KS B ISO 2768-m …'],EX_NOTE_ITEM:['注記に必要な項目がない','注記の中に必要な記載が見つかりませんでした。','不足している項目（普通公差、仕上げ区分、面取り・フィレットの規定など）を注記に補ってください。'],EX_NO_TITLEBLOCK:['表題欄・図面様式がない','表題欄や図面様式（輪郭線・中心マークを含む）が確認できません。','シートを右クリック > 表題欄の挿入 を行い、輪郭線と中心マークを配置してください。'],EX_NO_HEAT:['熱処理・表面処理の指示がない','注記に熱処理や表面処理の指示がありません。軸・歯車のような部品は「材料の選択と処理」で減点される可能性があります。','「全体熱処理 HRC 50±0.2」のような指示を追加し、材料記号（SM45C、SCM415、GC200）は部品欄に記入してください。'],EX_FEW_VIEWS:['投影図が {n} 個のみ','部品形状を表現するには投影図が不足しているように見えます。','正面図を基準に平面図・側面図を、必要なら断面図・詳細図を配置してください。'],EX_NO_CENTERLINE:['中心線・中心マークがない','円・穴に中心線や中心マークがありません。KS 製図規格違反です。','注釈 > 中心線 / 中心マーク ですべての円と対称形状に入れてください。'],EX_VIEW_NO_LABEL:['ビューに表示文字がない','断面図・詳細図はどの部分か分かるように文字（A、B…）と尺度を表記する必要があります。','ビューを右クリック > 編集 で「ラベル表示」と「尺度表示」をオンにしてください。'],EX_VIEW_NO_SCALE:['尺度表記のない拡大・縮小ビュー','図面全体の尺度と異なるビューは、その横に尺度を併記する必要があります。','ビューの編集で「尺度表示」をオンにしてください。'],EX_SHEET_SIZE:['図面領域が要求サイズと異なります','公開問題の要求は A2 への作図で、A3 は出力用紙のサイズです。回次の指示事項が優先されます。','シートを A2（594×420 mm）にし、出力のみ A3 で行ってください。'],EX_NO_PROJECTION_MARK:['投影法の表記がありません','表題欄に「第三角法」の表記や投影法記号が見つかりません。投影法の表記は必須項目です。','表題欄の角法欄に第三角法を記入し、投影法記号も入れてください。'],EX_NO_SHEET_SCALE:['表題欄に尺度の表記がありません','表題欄の尺度欄が見つかりません。尺度は表題欄の必須項目です。','尺度欄に 1:1（3D 等角投影図は NS）を記入してください。'],EX_SCALE_NOT_ONE:['部品図の尺度が 1:1 ではありません','公開問題は部品図を尺度 1:1 で要求しています。','表題欄とビューの尺度を 1:1 に合わせてください。'],EX_VIEW_SCALE_MIXED:['尺度が 1:1 でないビューが {n} 個','部品図は尺度 1:1 が要求されます。詳細図として意図的に拡大したものはそのままで構いません。','ビューの尺度を確認し、詳細図でなければ 1:1 に戻してください。'],EX_NO_MATERIAL:['材料記号がありません','表題欄・部品欄に材料記号（SM45C、SCM415、GC250 など）が見つかりません。材料の記入は「材料の選択と処理」の採点項目です。','部品欄の材質欄に部品ごとの KS 材料記号を記入してください。'],EX_NO_MASS:['等角投影図の部品欄に質量がありません','3D レンダリング等角投影図は、部品欄の備考に各部品の質量を g 単位（小数第一位を四捨五入）で記入する必要があります。','Inventor の ファイル > iProperties > 物理 で材質を指定して更新し、質量値を部品欄の備考に記入してください。'],EX_RULE_ERROR:['検査エラー','この図面に対して検査を完了できませんでした。','この結果をご報告ください。'],DQ_NO_FIT:['失格: はめあい公差記号なし','H7、js5、h6 のようなはめあい公差記号が一つもありません。部品図にはめあい公差記号を記入していない図面は失格です。','結合する寸法にはめあい記号を入れてください。例）軸受軸 Ø17js5、カバー穴 Ø47H7'],EX_NO_ROUGH_TABLE:['表面粗さ比較表がありません','面に粗さ記号を {n} 個記入していますが、仕上げ区分を定義する比較表が見つかりません。比較表がないと w・x・y がそれぞれどの粗さか分かりません。','図面上部の空いた所に √(√w, √x, √y) 形式の比較表を入れ、注記で仕上げの程度を定義してください。'],EX_NO_SPEC_TABLE:['歯車・ばねの要目表がありません','部品欄に歯車またはばねがありますが、要目表が見つかりません。歯車・ばねは形状寸法だけでは作れないため、歯数・モジュール・圧力角などを要目表に別途記入する必要があります。','空いた所に要目表を描き、歯形・モジュール・圧力角・歯数・ピッチ円直径・仕上げ方法・精度を記入してください。'],EX_LINEWEIGHT_NONE:['画層に線の太さが設定されていません','どの画層にも線の太さが設定されておらず、色で分けた形跡もありません。このまま出力すると外形線と寸法線が同じ太さになります。','画層プロパティで輪郭線 0.7、外形線 0.5、かくれ線 0.35、中心線・寸法線 0.25、ハッチング 0.18 mm に設定してください。色で太さを出す方式なら出力ペン設定を確認してください。'],EX_LINEWEIGHT_FLAT:['外形線と細線の太さの差が小さい（{n}倍）','KS 製図規格は 細線 : 太線 = 1 : 2 以上を求めています。線の太さが区別されていないと図面が読みにくく、減点されます。','外形線を 0.5 mm、寸法線・中心線を 0.25 mm にするとちょうど2倍になります。'],EX_TEXT_SIZE:['寸法文字の高さが {n} mm です','KS の文字高さは決められた呼び寸法（2.24・2.5・3.15・3.5・4.5・5・6.3・7・9・10 mm）から選び、最小は 2.5 mm です。実技図面の寸法文字は普通 3.15 または 3.5 mm です。','寸法スタイルの編集で文字高さを 3.15 または 3.5 mm に変更してください。'],EX_LAYOUT_FIRST_ANGLE:['ビューの配置が第一角法に見えます','正面図と揃った投影図が第一角法の側にしかありません。第三角法では平面図が上、右側面図が右です。要求と異なる投影法は失格です。','平面図を正面図の上、右側面図を正面図の右に置いてください。下面図・左側面図だけを使った場合はそのままで構いません。']},
zh:{DQ_NO_SURFACE_SYMBOL:['失格：无表面粗糙度符号','零件图中没有任何表面粗糙度符号。按公开的评分标准，零件图未标注表面粗糙度符号即为失格。','在“注释 > 表面结构符号”中为每个加工面标注符号，并在注释中定义精加工等级（w/x/y 或 Ra 值）。'],DQ_NO_GEOMETRIC_TOL:['失格：无几何公差符号','零件图中没有任何几何公差框格。零件图未标注几何公差即为失格。','先指定基准（A、B…），再标注同轴度、垂直度、平行度等。'],DQ_PROJECTION:['失格：使用了第一角法','要求使用第三角法，但图纸为第一角法。投影法与要求不符的图纸判为失格。','在“管理 > 样式编辑器 > 制图标准”中改为第三角法，并核对标题栏的投影法符号。'],DQ_SHEET_SIZE:['失格：图幅尺寸不符','图幅不是要求的尺寸。未按要求图幅绘制的作品判为失格。','右键单击图纸 > 编辑图纸，改为要求的尺寸。'],DQ_SCALE:['失格风险：非标准比例','该比例不属于 KS 标准比例。','将视图比例改为 1:1、1:2、2:1 等标准值。'],EX_NO_DIMS:['完全没有尺寸','图纸中没有标注任何尺寸，尺寸标注的 15 分将全部失去。','使用“注释 > 尺寸”标注主要尺寸。'],EX_DIM_MISSING:['疑似漏标尺寸 {n} 处','存在没有标注尺寸的圆或孔。漏标尺寸会直接扣分。','为相应形状补充尺寸。若多个孔尺寸相同，可合并标注一次，如“4-Ø6”。'],EX_TOL_FEW:['标注公差的尺寸偏少','带公差的尺寸比例偏低。功能尺寸需要公差。','先从参与装配和配合的尺寸开始标注公差。'],EX_SURFACE_EMPTY:['有 {n} 个表面粗糙度符号未填数值','部分表面粗糙度符号没有数值。只有符号而无数值，无法构成加工要求。','双击符号填入数值，例如 w/x/y 或 Ra 1.6、Ra 6.3。'],EX_SURFACE_UNIFORM:['粗糙度只用了一种数值','所有表面标注了相同的粗糙度。配合面、轴承接触面应与一般加工面区分精加工程度。','按功能区分，例如配合面 y、一般加工面 x、黑皮面不去除加工。'],EX_SURFACE_FEW:['表面粗糙度符号只有 {n} 个','相对于加工面，符号数量偏少。每个功能面都应标注。','对配合面、轴承接触面、滑动面分别标注。'],EX_FCF_NO_DATUM:['所有几何公差都没有基准','几何公差框格的基准栏全部为空。垂直度、平行度、同轴度、位置度和跳动没有基准就没有意义。','为主要轴线或表面指定基准（A、B…），再填入框格的基准栏。'],EX_FCF_NO_VALUE:['有 {n} 个几何公差未填公差值','只有符号而没有公差值。','双击框格填入公差值，例如 0.011。'],EX_FCF_FEW:['几何公差只有 {n} 个','通常需要以基准为参照标注两项以上，如同轴度、垂直度或平行度。','补充以基准 A 为参照的同轴度、端面垂直度等。'],EX_NO_NOTES:['没有技术要求（注释）','图纸没有技术要求。未写明未注公差、倒角、热处理和表面处理会被扣分。','例如：1. 未注公差 - a) 加工部位：KS B ISO 2768-m …'],EX_NOTE_ITEM:['技术要求缺少必要条目','在技术要求中未找到必须写明的条目。','补上缺少的条目，如未注公差、精加工等级、倒角与圆角的规定。'],EX_NO_TITLEBLOCK:['没有标题栏或图框','未能确认标题栏或图纸格式（含图框线和中心标记）。','右键单击图纸 > 插入标题栏，并放置图框线和中心标记。'],EX_NO_HEAT:['没有热处理或表面处理说明','技术要求中没有热处理或表面处理说明。轴、齿轮这类零件可能在“材料与处理”项失分。','补充“整体热处理 HRC 50±0.2”之类的说明，材料牌号（SM45C、SCM415、GC200）写入明细栏。'],EX_FEW_VIEWS:['视图只有 {n} 个','视图数量似乎不足以表达零件形状。','以主视图为基准布置俯视图和侧视图，必要时增加剖视图和局部放大图。'],EX_NO_CENTERLINE:['没有中心线或中心标记','圆和孔没有中心线或中心标记，违反 KS 制图规范。','使用“注释 > 中心线 / 中心标记”为所有圆和对称形状添加。'],EX_VIEW_NO_LABEL:['视图没有标识字母','剖视图和局部放大图必须标注字母（A、B…）和比例，以便识别所示部位。','右键单击视图 > 编辑，打开标签显示和比例显示。'],EX_VIEW_NO_SCALE:['放大或缩小视图未标注比例','与图纸总比例不同的视图，必须在其旁边标注该比例。','在视图设置中打开比例显示。'],EX_SHEET_SIZE:['图纸区域与要求尺寸不符','公开试题要求在 A2 图幅上绘制，A3 是打印纸尺寸。以本次考试的指示事项为准。','将图纸设置为 A2（594×420 mm），仅打印时使用 A3。'],EX_NO_PROJECTION_MARK:['缺少投影法标注','标题栏中找不到第三角法标注或投影法符号。投影法标注为必填项。','在标题栏的角法栏填写第三角法，并加上投影法符号。'],EX_NO_SHEET_SCALE:['标题栏没有比例标注','找不到标题栏的比例栏。比例是标题栏的必填项。','在比例栏填写 1:1（3D 等轴测图为 NS）。'],EX_SCALE_NOT_ONE:['零件图比例不是 1:1','公开试题要求零件图使用 1:1 比例。','将标题栏和视图比例设置为 1:1。'],EX_VIEW_SCALE_MIXED:['有 {n} 个视图不是 1:1','零件图要求 1:1。若为局部放大图而有意放大，可保持不变。','检查视图比例，若非局部放大图请改回 1:1。'],EX_NO_MATERIAL:['没有材料牌号','在标题栏或明细栏中未找到材料牌号（如 SM45C、SCM415、GC250）。材料标注属于材料与处理评分项。','在明细栏的材质列为每个零件填写 KS 材料牌号。'],EX_NO_MASS:['等轴测图明细栏没有质量','3D 渲染等轴测图必须在明细栏备注中以克为单位（小数点后一位四舍五入）标注各零件质量。','在 Inventor 的 文件 > iProperties > 物理 中指定材质并更新，然后将质量值填入明细栏备注。'],EX_RULE_ERROR:['检查规则出错','该图纸的某项检查未能完成。','请反馈此结果以便核查。'],DQ_NO_FIT:['失格：没有配合公差符号','没有 H7、js5、h6 之类的配合公差符号。零件图未标注配合公差符号即为失格。','在配合尺寸上加配合符号，例如轴承轴 Ø17js5、端盖孔 Ø47H7。'],EX_NO_ROUGH_TABLE:['没有表面粗糙度对照表','表面上标注了 {n} 个粗糙度符号，但没有找到定义加工等级的对照表。没有对照表就无法知道 w、x、y 分别代表哪种粗糙度。','在图纸上方空白处加入 √(√w, √x, √y) 形式的对照表，并在技术要求中定义加工程度。'],EX_NO_SPEC_TABLE:['没有齿轮或弹簧参数表','明细栏中有齿轮或弹簧，但没有找到参数表。齿轮和弹簧仅凭形状尺寸无法制造，齿数、模数、压力角等数值必须另列参数表。','在空白处绘制参数表，填写齿形、模数、压力角、齿数、分度圆直径、加工方法和精度。'],EX_LINEWEIGHT_NONE:['图层未设置线宽','所有图层都没有设置线宽，也没有按颜色区分的迹象。直接打印时轮廓线和尺寸线会一样粗。','在图层特性中设置图框线 0.7、轮廓线 0.5、虚线 0.35、中心线和尺寸线 0.25、剖面线 0.18 mm。如果用颜色控制线宽，请检查打印笔设置。'],EX_LINEWEIGHT_FLAT:['轮廓线与细线的线宽差太小（{n}倍）','KS 制图标准要求 细线 : 粗线 = 1 : 2 以上。线宽没有区分会使图纸难以阅读并被扣分。','把轮廓线设为 0.5 mm、尺寸线和中心线设为 0.25 mm，正好是 2 倍。'],EX_TEXT_SIZE:['尺寸文字高度为 {n} mm','KS 文字高度须从规定的公称尺寸（2.24、2.5、3.15、3.5、4.5、5、6.3、7、9、10 mm）中选择，最小为 2.5 mm。实操图纸的尺寸文字通常为 3.15 或 3.5 mm。','在标注样式编辑中把文字高度改为 3.15 或 3.5 mm。'],EX_LAYOUT_FIRST_ANGLE:['视图布局看起来是第一角法','与主视图对齐的视图只出现在第一角法的位置。第三角法中俯视图在上方，右视图在右侧。与要求不同的投影法会被判失格。','把俯视图放在主视图上方、右视图放在主视图右侧。如果只用了仰视图和左视图，可以保持不变。']}
};
function findingText(f){const ai=(f.i18n||{})[lang];if(ai&&(ai.title||ai.detail))return{title:ai.title||f.title,detail:ai.detail||'',fix:ai.fix||''};const saved=(FINDING_I18N[lang]||{})[f.code];if(saved){const raw=[f.title,f.detail,f.fix].join(' ');const nums=[...raw.matchAll(/[-+]?\d+(?:\.\d+)?/g)].map(x=>x[0]);const where=Object.values(f.where||{}).filter(Boolean).join(' · ')||'';const vals={n:nums[0]||'',d:nums[0]||'',v:nums.slice(0,4).join(' / '),where};const fill=s=>s.replace(/\{(\w+)\}/g,(_,k)=>vals[k]??'');return{title:fill(saved[0]),detail:fill(saved[1]),fix:fill(saved[2])}}if(lang==='ko')return{title:f.title,detail:f.detail,fix:f.fix};const label=(CHECK_LABELS[lang]||{})[f.code]||f.code;const generic={en:['The drawing does not meet this check requirement.','Review the marked drawing content and correct it before submission.'],ja:['この図面は検査条件を満たしていません。','指摘された図面内容を確認し、提出前に修正してください。'],zh:['该图纸未满足此检查要求。','请检查标记的图纸内容，并在提交前修正。']}[lang];return{title:label,detail:generic[0],fix:generic[1]}}

const SEV={fail:'var(--red)',error:'var(--red)',warn:'var(--amber)',info:'var(--soft)'};
const SEV_ICON={fail:'fail',error:'error',warn:'warn',info:'info'};
let CHECKS=[],enabled=new Set(),HEALTH={},RES=null,RAW=null,sevFilter=null,STATS=null,SAMPLES=[],busyNow=false,busyTimer=0;
const LS='cadcheck.enabled';const picked=()=>[...enabled];

function setTitle(file){document.title=file?`${file} · CADLens`:`CADLens | ${t('brandSub')}`}
onLang.push(()=>{
  $('.hero-t').innerHTML=esc(t('heroTitle')).replace(/^(.+?[,，、.])\s*/,'$1<br>');  // break after the first clause
  $('#ctaBandT').textContent=t('guide')[0][0];
  drawHealth();drawRubric();drawPicker();drawStats();drawFaq();drawSamples();
  if(!$('#guide').hidden)drawGuide();
  if(RAW)render(RAW,true);else setTitle();
});

// OGQ 마켓 캐릭터 스티커(서버가 키를 가지고 받아 둔다). 서버에 키가 없으면 아무것도 안 그린다.
const stk=(name,cls='')=>HEALTH.stickers?`<img class="stk ${cls}" src="/api/sticker/${name}" alt="" width="240" height="207" onerror="this.remove()">`:'';
function showErr(msg){const box=$('#res').hidden?$('#errHome'):$('#errRes');box.innerHTML=`${stk('error','sm')||ico('error')}<span>${esc(msg)}</span>`;box.classList.remove('hide');box.scrollIntoView({block:'center'})}
function clearErr(){$('#errHome').classList.add('hide');$('#errRes').classList.add('hide')}

function drawHealth(){const h=HEALTH;if(!h||!h.ok)return;const sup=h.supported||[];$('#stkCredit').hidden=!h.stickers;
  $('#exts').textContent=sup.join(' · ')||'.dwg · .dxf';
  $('#formatrow').innerHTML=sup.map(x=>`<span class="chip">${esc(x)}</span>`).join('')+'<span class="chip">zip</span>';
  const bits=[];if(h.exam)bits.push(`${h.exam.sheet} ${t('examBase')}`);bits.push(`${CHECKS.length} ${t('checks')}`);bits.push(h.ai?t('aiOn'):t('aiOff'));if(h.dwg_via)bits.push(t('dwgReady'));
  $('#foot').textContent=bits.join(' · ')}
fetch('/api/health').then(r=>r.json()).then(h=>{HEALTH=h;CHECKS=h.checks||[];let saved=null;try{saved=JSON.parse(store.get(LS))}catch(e){}
  const kept=Array.isArray(saved)?saved.filter(id=>CHECKS.some(c=>c.id===id)):[];
  enabled=new Set(kept.length?kept:CHECKS.filter(c=>c.default).map(c=>c.id));FMT.n=CHECKS.length;applyLang()})
  .catch(()=>showErr(t('appError')));

function drawRubric(){const names=t('rub'),tone=[0,100,84,70,58,48,38,30];
  const col=i=>i?`var(--cyan);opacity:${tone[i]/100}`:'var(--violet)';
  $('#rvis').innerHTML=RUBRIC_CODES.map((c,i)=>`<i style="flex:${RUBRIC_MAX[i]};background:${col(i)}"></i>`).join('');
  $('#rubric').innerHTML=RUBRIC_CODES.map((c,i)=>`<li><span class="sw" style="background:${col(i)}"></span><span class="nm">${esc(names[i])}</span><span class="mode${i?'':' ai'}">${i?esc(t('modeRule')):'AI'}</span><span class="pt">${RUBRIC_MAX[i]}</span></li>`).join('');
  const dq=CHECKS.filter(c=>GROUP_BY_CHECK[c.id]==='dq');$('#dqsec').classList.toggle('hide',!dq.length);
  $('#dqlist').innerHTML=dq.map(c=>`<li>${esc(translatedCheck(c))}</li>`).join('')}

function drawPicker(){if(!CHECKS.length)return;const groups=[];
  CHECKS.forEach(c=>{let g=groups.find(x=>x.key===c.group);if(!g)groups.push(g={key:c.group,label:groupLabel(c),items:[]});g.items.push(c)});
  $('#pbody').innerHTML=groups.map(g=>`<div class="pgroup"><h4>${esc(g.label)}</h4>${g.items.map(c=>`<label><input type="checkbox" data-id="${esc(c.id)}" ${enabled.has(c.id)?'checked':''}><span>${esc(translatedCheck(c))}</span></label>`).join('')}</div>`).join('');
  $('#pbtns').innerHTML=[['all','allOn'],['none','allOff'],['def','basic']].map(([p,k])=>`<button class="btn btn-ghost" type="button" data-p="${p}">${esc(t(k))}</button>`).join('');
  $$('#pbody input').forEach(el=>el.onchange=()=>{el.checked?enabled.add(el.dataset.id):enabled.delete(el.dataset.id);persist()});
  $$('#pbtns button').forEach(b=>b.onclick=()=>{const p=b.dataset.p;enabled=new Set(p==='all'?CHECKS.map(c=>c.id):p==='none'?[]:CHECKS.filter(c=>c.default).map(c=>c.id));drawPicker()});
  persist()}
function persist(){store.set(LS,JSON.stringify([...enabled]));$('#pcount').textContent=`${enabled.size}/${CHECKS.length}`;if(enabled.size)clearErr()}
$('#ptoggle').onclick=()=>{const p=$('#ppanel');p.hidden=!p.hidden;$('#ptoggle').setAttribute('aria-expanded',String(!p.hidden))};

function loadStats(){fetch('/api/stats').then(r=>r.json()).then(s=>{STATS=s;drawStats()}).catch(()=>{})}
function drawStats(){const s=STATS;if(!s||!s.available)return;$('#statbox').classList.remove('hide');const p=t('statPeople'),c=t('statTimes');
  $('#statVisit').textContent=s.week.visitors+p;$('#statVisitD').textContent=`${t('statToday')} ${s.today.visitors}${p} · ${t('statAll')} ${s.total.visits}${c}`;
  $('#statCheck').textContent=s.week.checks+c;$('#statCheckD').textContent=`${t('statToday')} ${s.today.checks}${c} · ${t('statAll')} ${s.total.checks+s.total.samples}${c}`;
  $('#statAgain').textContent=s.week.recheckers+p;$('#statAgainD').textContent=(s.week.rechecks?`${t('statWeek')} ${s.week.rechecks}${c} · `:'')+t('statAgainD');
  $('#statNote').textContent=fmt(t('statNote'),{since:s.total.since,days:s.total.days})}

function drawFaq(){const open=$$('#faqList details').map(d=>d.open);
  $('#faqList').innerHTML=t('faq').map(([q,a],i)=>`<details${open[i]?' open':''}><summary>${esc(q)}${ico('chev')}</summary><p>${esc(a)}</p></details>`).join('')}

fetch('/api/samples').then(r=>r.json()).then(d=>{SAMPLES=(d&&d.samples)||[];drawSamples()}).catch(()=>{});
function drawSamples(){const has=SAMPLES.length>0;$('#samples').classList.toggle('hide',!has);$('#ctaSample').classList.toggle('hide',!has);if(!has)return;
  const notes=lang==='ko'?{}:t('sampleNote');
  $('#sgrid').innerHTML=SAMPLES.map(s=>`<button class="scard" type="button" data-n="${esc(s.name)}"><span class="sext">${esc(s.ext.replace('.',''))}</span><b>${esc(s.name)}</b><p>${esc(notes[s.name]||s.note||'')}</p><span class="smeta"><span>${kb(s.size)}</span><span>${esc(t('sampleRun'))}${ico('arrow')}</span></span></button>`).join('');
  $$('#sgrid .scard').forEach(b=>b.onclick=()=>sendSample(b.dataset.n))}

function ready(){if(busyNow)return false;if(!CHECKS.length){showErr(t('appError'));return false}if(!enabled.size){showErr(t('noChecks'));return false}clearErr();return true}
function busy(label){busyNow=true;$('#busyFile').textContent=label;const sp=$('.spin');if(!sp.querySelector('.stk'))sp.insertAdjacentHTML('afterbegin',stk('wait'));const t0=Date.now();
  const tick=()=>{$('#busyTime').textContent=fmt(t('elapsed'),{s:Math.floor((Date.now()-t0)/1000)})};tick();busyTimer=setInterval(tick,1000);$('#busy').hidden=false}
function idle(){busyNow=false;clearInterval(busyTimer);$('#busy').hidden=true}
const done=r=>r.json().catch(()=>({detail:'Bad response'})).then(j=>{if(!r.ok)throw new Error(j.detail||r.status);loadStats();return j});
function fail(e){const d=lang==='ko'?String((e&&e.message)||'').trim().replace(/^분석 실패:\s*/,''):'';showErr(`${t('failed')}: ${d||t('failCopy')}`)}
function run(req,label){busy(label);req.then(done).then(j=>render(j)).catch(fail).finally(idle)}
const sendSample=n=>{if(ready())run(fetch('/api/analyze-sample',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,checks:picked()})}),n)};
function send(f){if(!ready())return;const fd=new FormData();fd.append('file',f);fd.append('checks',picked().join(','));run(fetch('/api/analyze',{method:'POST',body:fd}),f.name)}
function pick(){if(ready())$('#file').click()}
// Clearing value lets the user pick the SAME file again after fixing it in CAD;
// otherwise the browser sees no change and never fires this handler a second time.
$('#file').onchange=e=>{const f=e.target.files[0];e.target.value='';if(f)send(f)};
['#ctaUpload','#ctaUpload2','#reup'].forEach(s=>$(s).onclick=pick);
const drop=$('#drop');
drop.onclick=pick;
drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}};
['dragenter','dragover'].forEach(x=>drop.addEventListener(x,e=>{e.preventDefault();drop.classList.add('over')}));
['dragleave','drop'].forEach(x=>drop.addEventListener(x,e=>{e.preventDefault();drop.classList.remove('over')}));
drop.addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(f)send(f)});
// A file dropped just outside the drop zone (or on the result page) would make the browser open it and leave the site.
['dragover','drop'].forEach(x=>addEventListener(x,e=>e.preventDefault()));
$('#ctaSample').onclick=()=>{$('#samples').scrollIntoView({block:'start'});const b=$('#sgrid .scard');if(b)b.focus({preventScroll:true})};

const ART={
upload:'<svg viewBox="0 0 240 132" aria-hidden="true"><path class="art-thin" d="M60 86v18a10 10 0 0 0 10 10h100a10 10 0 0 0 10-10V86"/><rect class="art-sheet" x="92" y="16" width="56" height="74" rx="8"/><path class="art-thin" d="M104 38h32M104 48h32M104 58h20"/><rect class="art-chip" x="100" y="68" width="40" height="15" rx="7.5"/><text class="art-chiptxt" x="120" y="75.5">DXF</text><path class="art-dim" d="M192 84V44M180 56l12-12 12 12"/></svg>',
check:'<svg viewBox="0 0 240 132" aria-hidden="true"><rect class="art-sheet" x="48" y="12" width="144" height="108" rx="14"/><circle class="art-ok" cx="72" cy="36" r="8"/><path class="art-tick" d="M68 36l3 3 5-6"/><path class="art-thin" d="M90 36h60"/><circle class="art-ok" cx="72" cy="59" r="8"/><path class="art-tick" d="M68 59l3 3 5-6"/><path class="art-thin" d="M90 59h78"/><circle class="art-badge" cx="72" cy="82" r="8"/><path class="art-tick" d="M69 79l6 6M75 79l-6 6"/><path class="art-thin" d="M90 82h50"/><circle class="art-ok" cx="72" cy="105" r="8"/><path class="art-tick" d="M68 105l3 3 5-6"/><path class="art-thin" d="M90 105h66"/></svg>',
marker:'<svg viewBox="0 0 240 132" aria-hidden="true"><rect class="art-sheet" x="30" y="12" width="180" height="108" rx="12"/><rect class="art-line" x="54" y="38" width="100" height="62" rx="6"/><circle class="art-line" cx="88" cy="69" r="12"/><path class="art-center" d="M70 69h36M88 51v36"/><circle class="art-ring" cx="88" cy="69" r="19"/><path class="art-lead" d="M103 57l50-20"/><circle class="art-badge" cx="164" cy="32" r="12"/><text class="art-num" x="164" y="32">1</text><path class="art-cursor" d="M170 40l13 30 5-11 11-5z"/></svg>',
compare:'<svg viewBox="0 0 240 132" aria-hidden="true"><rect class="art-sheet" x="18" y="24" width="86" height="86" rx="16"/><text class="art-big" x="61" y="60">62%</text><rect class="art-bad" x="39" y="80" width="44" height="10" rx="5"/><path class="art-dim" d="M114 67h18M124 59l8 8-8 8"/><rect class="art-sheet ok" x="142" y="24" width="86" height="86" rx="16"/><text class="art-big ok" x="185" y="60">88%</text><rect class="art-good" x="163" y="80" width="44" height="10" rx="5"/><circle class="art-ok" cx="224" cy="28" r="10"/><path class="art-tick" d="M219 28l3.5 3.5 6-7"/></svg>'};
$$('[data-art]').forEach(el=>el.innerHTML=ART[el.dataset.art]);

let gi=0,gReturn=null;
function openGuide(i){gi=i||0;gReturn=document.activeElement;$('#guide').hidden=false;document.body.style.overflow='hidden';drawGuide();$('#gNext').focus()}
function closeGuide(){$('#guide').hidden=true;document.body.style.overflow='';store.set('cadcheck.intro','1');if(gReturn&&gReturn.focus)gReturn.focus()}
function drawGuide(){const g=t('guide'),n=g.length;
  $('#gArt').innerHTML=gi?ART[['','upload','marker','compare'][gi]]:$('.drop-art').outerHTML;
  $('#gStep').textContent=`${gi+1} / ${n}`;$('#gTitle').textContent=g[gi][0];$('#gText').textContent=fmt(g[gi][1],FMT);
  $('#gDots').innerHTML=g.map((_,i)=>`<button type="button" class="${i===gi?'on':''}" aria-label="${i+1} / ${n}"${i===gi?' aria-current="step"':''}></button>`).join('');
  $$('#gDots button').forEach((b,i)=>b.onclick=()=>{gi=i;drawGuide()});
  $('#gPrev').style.visibility=gi?'visible':'hidden';$('#gNext').textContent=t(gi===n-1?'start':'next')}
$('#gNext').onclick=()=>{if(gi>=t('guide').length-1)closeGuide();else{gi++;drawGuide()}};
$('#gPrev').onclick=()=>{if(gi>0){gi--;drawGuide()}};
$$('#guide [data-close]').forEach(el=>el.onclick=closeGuide);
$('#guideBtn').onclick=()=>openGuide(0);
document.addEventListener('keydown',e=>{if($('#guide').hidden)return;
  if(e.key==='Escape'){closeGuide();return}
  if(e.key==='ArrowRight'&&gi<t('guide').length-1){gi++;drawGuide();return}
  if(e.key==='ArrowLeft'&&gi>0){gi--;drawGuide();return}
  if(e.key!=='Tab')return;
  const f=$$('#guide button').filter(b=>b.offsetParent&&b.style.visibility!=='hidden'),first=f[0],last=f[f.length-1];
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}});

function showView(v){const res=v==='res';$('#home').hidden=res;$('#res').hidden=!res}
function goHome(){showView('home');clearErr();setTitle();window.scrollTo(0,0)}
$('#back').onclick=goHome;
$$('[data-nav]').forEach(a=>a.onclick=e=>{if($('#res').hidden)return;e.preventDefault();goHome();const el=a.hash&&$(a.hash);if(el)el.scrollIntoView()});
['#brand','#brand2'].forEach(s=>$(s).onclick=e=>{e.preventDefault();if($('#res').hidden)window.scrollTo(0,0);else goHome()});

// One pass, no wrappers: keep the raw server payload, translate a copy of it,
// draw the result, then draw the comparison against the previous run.
function localize(d){const findings=(d.findings||[]).map(f=>({...f,...findingText(f),item:f.item?itemLabel(f.item):f.item}));const scorecard={...(d.scorecard||{})};scorecard.items=(scorecard.items||[]).map(it=>({...it,label:(CHECK_LABELS[lang]||{})[it.code]||it.label}));if(lang!=='ko'){scorecard.disqualifiers=findings.filter(f=>f.severity==='fail').map(f=>f.title);if(scorecard.ai_verdict)scorecard.ai_verdict=(scorecard.ai_verdict_i18n||{})[lang]||{en:'AI review is available for human confirmation.',ja:'AI レビューは人による確認用に表示されています。',zh:'AI 检查结果仅供人工确认。'}[lang]}d={...d,findings,scorecard};return{...d,svg_note:lang==='ko'?d.svg_note:(d.svg_note?t('previewNone'):'')}}
function render(raw,relang){
  if(!RAW||RAW.job!==raw.job){sevFilter=null;setTab('find');$('#finds').innerHTML=''}   // a new drawing clears the filter and tab
  RAW=raw;
  const diff=compareFor(raw);
  const d=RES=localize(raw);
  if(!relang){showView('res');clearErr();window.scrollTo(0,0)}
  setTitle(d.file);
  $('#rfile').textContent=d.file||'';
  const meta=[t('kind')[d.kind]||d.kind];if(d.standard)meta.push(d.standard);if(d.first_angle!==null&&d.first_angle!==undefined)meta.push(t(d.first_angle?'angle1':'angle3'));meta.push('Job '+d.job);
  $('#rmeta').textContent=meta.filter(Boolean).join(' · ');
  drawScore(d.scorecard||{},d.summary||{});drawItems(d.scorecard||{});drawFindings(d);drawInfo(d);drawSvg(d,relang);
  let disc=t('disc');const sc=d.scorecard||{};if(sc.review_points>0)disc+=` ${sc.review_points}${t('reviewPoints')}`;$('#disc').textContent=disc;
  drawCompare(diff);
  if(raw.ai_extra&&!relang)waitExtras(raw.job);
}

// Scores and findings arrive first; the AI answers and translations follow a few seconds later.
function waitExtras(job){
  let tries=0;
  const poll=()=>{if(!RAW||RAW.job!==job)return;
    fetch(`/api/ai-extra/${job}`).then(r=>r.ok?r.json():{ready:true,findings:[]}).catch(()=>null).then(x=>{
      if(!RAW||RAW.job!==job)return;
      if(!x||!x.ready){if(++tries<120)setTimeout(poll,1500);else{RAW.ai_extra=false;render(RAW,true)}return}
      const byIndex=new Map((x.findings||[]).map(e=>[e.ai_index,e]));
      RAW.findings.forEach(f=>{const e=f.code==='AI_PROJECTION'&&byIndex.get(f.ai_index);if(e){f.i18n=e.i18n;f.followups=e.followups}});
      if(RAW.scorecard&&x.verdict_i18n)RAW.scorecard.ai_verdict_i18n=x.verdict_i18n;
      RAW.ai_extra=false;render(RAW,true);
    })};
  setTimeout(poll,1500);
}

// 실기는 100점 만점 60점 이상 합격이다. 자동 채점 퍼센트가 60% 이상이면 합격선으로 본다.
// 공식 채점이 아니므로 '합격'이 아니라 '합격선'이라고 쓴다.
const PASS_MARK=60;
function drawScore(sc,sum){
  const note=`<p class="vnote">${esc(t('vdNote'))}</p>`;
  if(sc.disqualified){
    $('#score').innerHTML=`<div class="card dq"><span class="verdict bad">${ico('fail')}${esc(t('vdDq'))}</span>`
      +`<div class="dq-head">${stk('fail','pop')||`<span class="dq-ico">${ico('fail')}</span>`}<div><div class="dq-big">${esc(t('disqualified'))}</div><p class="dq-copy">${esc(t('dqCopy'))}</p></div></div>`
      +`<ul class="dq-list">${(sc.disqualifiers||[]).map(r=>`<li>${ico('x')}<span>${esc(r)}</span></li>`).join('')}</ul>${note}</div>`;
    return}
  const pct=sc.percent!=null?Math.round(sc.percent):0,ok=pct>=PASS_MARK,C=2*Math.PI*48;
  $('#score').innerHTML=`<div class="card"><div class="score-top">`
    +`<div class="gauge ${ok?'pass':'short'}" role="img" aria-label="${pct}%"><svg viewBox="0 0 116 116"><circle class="trk" cx="58" cy="58" r="48"/><circle class="val" cx="58" cy="58" r="48" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${C*(1-Math.min(100,Math.max(0,pct))/100)}"/></svg><b>${pct}%</b></div>`
    +`<div><span class="verdict ${ok?'good':'warn'}">${ico(ok?'check':'warn')}${esc(t(ok?'vdPass':'vdShort'))}</span><p class="score-sub">${esc(t('autoScore'))} <b>${sc.auto_score} / ${sc.auto_max}</b></p>${note}</div>${stk(ok?'pass':'short','pop')}</div>`
    +`<div class="counts">${['error','warn','info'].map(k=>`<div class="count" style="color:${SEV[k]}">${ico(SEV_ICON[k])}<span>${esc(t(k))}</span><b style="color:var(--text)">${sum[k]||0}</b></div>`).join('')}</div></div>`;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{const v=$('#score .val');if(v)v.style.strokeDashoffset=v.dataset.off}));
}
function drawItems(sc){
  $('#items').innerHTML=(sc.items||[]).map(it=>{const rev=it.mode==='review',ai=it.mode==='ai';const val=rev?`${t('review')} / ${it.max}`:`${it.score} / ${it.max}`;const w=rev||!it.max?0:(it.score/it.max)*100;
    return `<div class="item${ai?' ai':''}"><div class="item-top"><span>${esc((CHECK_LABELS[lang]||{})[it.code]||it.label)}${ai?` <span class="tag ai">${ico('spark')}AI</span>`:''}</span><span class="sc">${esc(val)}</span></div><div class="bar"><i style="width:${w}%"></i></div></div>`}).join('');
  $('#verdict').innerHTML=sc.ai_verdict?`<div class="ai-verdict"><b>${ico('spark')}${esc(t('aiTotal'))}</b>${esc(sc.ai_verdict)}</div>`:'';
}
function asksHtml(f){const a=(f.followups||{})[lang];if((!a||!a.length)&&f.code==='AI_PROJECTION'&&RAW&&RAW.ai_extra)return `<div class="askbar"><div class="asklab">${esc(t('askTitle'))}</div><p class="asknote" aria-live="polite">${esc(t('askPending'))}</p></div>`;if(!a||!a.length)return '';const qs=t('asks')||[];
  return `<div class="askbar"><div class="asklab">${esc(t('askTitle'))}</div><div class="asks">${a.map((_,i)=>`<button type="button" data-ask="${i}" aria-expanded="false">${esc(qs[i]||'')}</button>`).join('')}</div><div class="answer" aria-live="polite" hidden></div><p class="asknote">${esc(t('askNote'))}</p></div>`}
function drawFindings(d){
  // Redrawing (language change, late AI answers) keeps the cards the user had open.
  const opened=new Set($$('#finds .fhead[aria-expanded="true"]').map(h=>h.closest('.finding').dataset.i));
  const all=d.findings||[],counts={};all.forEach(f=>counts[f.severity]=(counts[f.severity]||0)+1);
  $('#cntFind').textContent=all.length;
  $('#fbar').innerHTML=[['',t('all'),all.length]].concat(Object.keys(SEV).filter(k=>counts[k]).map(k=>[k,t(k),counts[k]]))
    .map(([k,l,n])=>{const on=sevFilter===(k||null);return `<button type="button" data-s="${k}" class="${on?'on':''}" aria-pressed="${on}">${k?`<i style="background:${SEV[k]}"></i>`:''}${esc(l)} ${n}</button>`}).join('');
  $$('#fbar button').forEach(b=>b.onclick=()=>{sevFilter=b.dataset.s||null;$('#finds').innerHTML='';drawFindings(d)});
  const idx=d.markers_placed?(d.marker_index||[]):[];
  const shown=all.filter(f=>!sevFilter||f.severity===sevFilter);
  $('#finds').innerHTML=shown.map((f,i)=>{const sev=SEV[f.severity]?f.severity:'info';
    const marked=d.markers_placed&&(f.code==='DIM_MISSING'||f.code==='EX_DIM_MISSING'||f.code==='EX_NO_DIMS');
    const markers=marked?idx.filter(m=>!m.finding_code||m.finding_code===f.code||(f.code==='DIM_MISSING'&&m.finding_code==='EX_DIM_MISSING')):[];
    const tags=[`<span class="tag ${sev}">${esc(t(sev))}</span>`];
    if(f.code==='AI_PROJECTION')tags.push(`<span class="tag ai">${ico('spark')}AI</span>`);
    if(f.item)tags.push(`<span>${esc(f.item)}</span>`);
    if(f.deduct)tags.push(`<span class="tag ded">${f.deduct}${esc(t('deduct'))}</span>`);
    const w=f.where||{};const where=['sheet','view','sketch','feature'].filter(k=>w[k]).map(k=>esc(w[k])).join(' · ');
    return `<div class="finding" data-i="${i}"><button class="fhead" type="button" aria-expanded="false" aria-controls="fb-${i}"><span class="sev ${sev}">${ico(SEV_ICON[sev])}</span><span class="fmain"><span class="ftitle">${esc(f.title)}</span><span class="fmeta">${tags.join('')}</span></span>${ico('chev','chev')}</button>`
      +(markers.length?`<div class="markers">${markers.map(m=>`<button class="mchip" type="button" data-n="${m.n}" aria-label="${esc(fmt(t('markerGo'),{n:m.n}))}"><b>${m.n}</b>Ø${Number(m.diameter_mm).toFixed(1)} · ${m.count||1}${esc(t('places'))}</button>`).join('')}</div>`:'')
      +`<div class="fbody" id="fb-${i}" hidden>${f.detail?`<p>${esc(f.detail)}</p>`:''}${f.fix?`<div class="fix"><b>${ico('check')}${esc(t('fixLabel'))}</b>${esc(f.fix)}</div>`:''}${asksHtml(f)}${where?`<p class="fwhere">${esc(t('where'))} · ${where}</p>`:''}</div></div>`}).join('')
    ||`<div class="empty">${esc(t('emptyFindings'))}</div>`;
  $$('#finds .finding').forEach(el=>{const f=shown[+el.dataset.i],head=el.querySelector('.fhead'),body=el.querySelector('.fbody');
    head.onclick=()=>{const open=body.hidden;body.hidden=!open;head.setAttribute('aria-expanded',String(open))};
    if(opened.has(el.dataset.i)){body.hidden=false;head.setAttribute('aria-expanded','true')}
    const box=el.querySelector('.answer'),answers=(f.followups||{})[lang];if(!box||!answers)return;
    const asks=$$('.asks button',el);
    asks.forEach(b=>b.onclick=()=>{const open=!b.classList.contains('on');asks.forEach(x=>{x.classList.remove('on');x.setAttribute('aria-expanded','false')});
      if(open){b.classList.add('on');b.setAttribute('aria-expanded','true');box.textContent=answers[+b.dataset.ask]||'';box.hidden=false}else box.hidden=true})});
}
function drawInfo(d){const rows=[];
  // props also carries internal flags such as `_has_title_block`; those are not for people.
  Object.entries(d.props||{}).forEach(([k,v])=>{if(v&&!k.startsWith('_'))rows.push([t('prop')[k]||k,v])});
  Object.entries(d.stats||{}).forEach(([k,v])=>{if(v!==null&&v!==undefined&&v!==''&&k!=='kind')rows.push([t('stat')[k]||k,typeof v==='boolean'?(v?t('bool').yes:t('bool').no):v])});
  $('#tab-info').hidden=!rows.length;if(!rows.length&&curTab==='info')setTab('find');
  $('#igrid').innerHTML=rows.map(([l,v])=>`<div><span>${esc(l)}</span><b>${esc(v)}</b></div>`).join('')}

const TABS=['find','items','info'];let curTab='find';
function setTab(name,focus){curTab=name;TABS.forEach(n=>{const b=$('#tab-'+n),on=n===name;b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;$('#panel-'+n).hidden=!on});if(focus)$('#tab-'+name).focus()}
TABS.forEach(n=>$('#tab-'+n).onclick=()=>setTab(n));
$('.tabs').addEventListener('keydown',e=>{if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;e.preventDefault();
  const vis=TABS.filter(n=>!$('#tab-'+n).hidden),i=vis.indexOf(curTab);setTab(vis[(i+(e.key==='ArrowRight'?1:-1)+vis.length)%vis.length],true)});

let zoom=1,ox=0,oy=0,fitZoom=1,drag=null,stageSize='';const pan=$('#pan'),stage=$('#stage');
const ZOUT=.4,ZIN=45;
const clampZ=z=>fitZoom>0?Math.max(fitZoom*ZOUT,Math.min(fitZoom*ZIN,z)):z;
function apply(){pan.style.transform=`translate(${ox}px,${oy}px) scale(${zoom})`}
function showZoom(){$('#zoomv').textContent=Math.round(zoom/(fitZoom||1)*100)+'%'}
function fit(){const svg=pan.querySelector('svg');if(!svg)return;const r=stage.getBoundingClientRect();stageSize=Math.round(r.width)+'x'+Math.round(r.height);const w=svg.viewBox.baseVal.width||svg.clientWidth||1,h=svg.viewBox.baseVal.height||svg.clientHeight||1;zoom=Math.min(r.width/w,r.height/h)*.98;ox=(r.width-w*zoom)/2;oy=(r.height-h*zoom)/2;apply();fitZoom=zoom;showZoom()}
function setZoom(z,cx,cy){const r=stage.getBoundingClientRect();cx=cx==null?r.width/2:cx;cy=cy==null?r.height/2:cy;const next=clampZ(z);ox=cx-(cx-ox)*(next/zoom);oy=cy-(cy-oy)*(next/zoom);zoom=next;apply();showZoom()}
function drawSvg(d,keep){const has=!!d.svg;$('#viewer').classList.toggle('hide',!has);$('#novw').classList.toggle('hide',has||!d.svg_note);
  if(!has){if(d.svg_note)$('#novw').innerHTML=`${ico('warn')}<span>${esc(d.svg_note)}</span>`;return}
  if(keep){if(fixOn)drawFixNote(d);return}
  pan.innerHTML=d.svg;setFix(false);$('#fixBtn').hidden=!fixCounts(d);const svg=pan.querySelector('svg');if(svg&&svg.viewBox.baseVal.width){svg.setAttribute('width',svg.viewBox.baseVal.width);svg.setAttribute('height',svg.viewBox.baseVal.height)}requestAnimationFrame(fit)}
addEventListener('resize',()=>{if($('#res').hidden||$('#viewer').classList.contains('hide'))return;const r=stage.getBoundingClientRect();if(Math.round(r.width)+'x'+Math.round(r.height)!==stageSize)fit()});
stage.addEventListener('wheel',e=>{if(!pan.querySelector('svg'))return;e.preventDefault();const r=stage.getBoundingClientRect();pan.classList.add('dragging');setZoom(zoom*(e.deltaY<0?1.18:1/1.18),e.clientX-r.left,e.clientY-r.top)},{passive:false});
stage.addEventListener('pointerdown',e=>{if(!pan.querySelector('svg'))return;drag={x:e.clientX,y:e.clientY,ox,oy};stage.classList.add('grabbing');pan.classList.add('dragging');stage.setPointerCapture(e.pointerId)});
stage.addEventListener('pointermove',e=>{if(!drag)return;ox=drag.ox+(e.clientX-drag.x);oy=drag.oy+(e.clientY-drag.y);apply()});
const endDrag=()=>{drag=null;stage.classList.remove('grabbing')};
stage.addEventListener('pointerup',endDrag);stage.addEventListener('pointercancel',endDrag);
$('#zin').onclick=()=>{pan.classList.remove('dragging');setZoom(zoom*1.4)};
$('#zout').onclick=()=>{pan.classList.remove('dragging');setZoom(zoom/1.4)};
$('#zfit').onclick=()=>{pan.classList.remove('dragging');fit()};

// Fix preview: hole diameter callouts and center marks drawn straight onto the preview, in green.
// Positions come from the drawing's own coordinates (svg_tf maps DXF to SVG units); nothing is generated,
// and nothing is sent to the server, so it shows at once.
let fixOn=false;
const DIM_CODES=['EX_DIM_MISSING','EX_NO_DIMS'],CANT_CODES=['DQ_NO_SURFACE_SYMBOL','DQ_NO_GEOMETRIC_TOL','DQ_NO_FIT'];
function fixCounts(d){if(!d||!d.svg_tf)return null;
  const holes=d.markers_placed&&(d.findings||[]).some(f=>DIM_CODES.includes(f.code))?(d.marker_index||[]):[];
  const centers=(d.fix&&d.fix.centers)||[];
  return holes.length||centers.length?{holes,centers}:null}
function fixLayer(d){const c=fixCounts(d);if(!c)return '';
  const tf=d.svg_tf,K=(d.fix&&d.fix.mm_per_unit)||1,s=tf.scale;
  const X=x=>x*s+tf.off_x,Y=y=>tf.off_y-y*s,mm=v=>v/K*s,n=v=>+v.toFixed(3);  // mm on paper -> SVG units
  const out=[];
  c.centers.forEach(([x,y,r])=>{const cx=X(x),cy=Y(y),e=r*s+mm(3);
    out.push(`<path d="M${n(cx-e)} ${n(cy)}H${n(cx+e)}M${n(cx)} ${n(cy-e)}V${n(cy+e)}" stroke-dasharray="${n(mm(8))} ${n(mm(1.5))} ${n(mm(.8))} ${n(mm(1.5))}"/>`)});
  // Leader goes up-left: the numbered marker badge already sits up-right of the hole.
  c.holes.forEach(h=>{const cx=X(h.dxf_x),cy=Y(h.dxf_y),r=h.dxf_r*s,u=Math.SQRT1_2;
    const px=cx-r*u,py=cy-r*u,qx=px-mm(9)*u,qy=py-mm(9)*u,len=mm(3.5)*(String(+h.diameter_mm.toFixed(2)).length+1)*.62;
    const bx=px-mm(2.6)*u,by=py-mm(2.6)*u,w=mm(.9)*u;
    out.push(`<path d="M${n(px)} ${n(py)}L${n(qx)} ${n(qy)}H${n(qx-len)}"/>`,
      `<path class="fixfill" d="M${n(px)} ${n(py)}L${n(bx+w)} ${n(by-w)}L${n(bx-w)} ${n(by+w)}Z"/>`,
      `<text x="${n(qx-mm(.8))}" y="${n(qy-mm(1.2))}" text-anchor="end" font-size="${n(mm(3.5))}">Ø${+h.diameter_mm.toFixed(2)}</text>`)});
  return `<g class="fixlayer" stroke-width="${n(Math.max(mm(.5),tf.view_w/1600))}">${out.join('')}</g>`}
function drawFixNote(d){const c=fixCounts(d);if(!c)return;
  const bits=[];if(c.holes.length)bits.push(fmt(t('fixDims'),{n:c.holes.length}));if(c.centers.length)bits.push(fmt(t('fixCenters'),{n:c.centers.length}));
  const codes=new Set((d.findings||[]).map(f=>f.code));
  $('#fixNote').innerHTML=`<p><b>${esc(t('fixLegend'))}</b> ${esc(bits.join(' · '))}. ${esc(t('fixCheck'))}</p>`
    +(c.holes.some(h=>(h.count||1)>1)?`<p>${esc(t('fixSame'))}</p>`:'')
    +(CANT_CODES.some(k=>codes.has(k))?`<p class="cant">${esc(t('fixCant'))}</p>`:'')}
function setFix(on){const svg=pan.querySelector('svg');fixOn=!!(on&&svg&&fixCounts(RES));
  if(fixOn&&!svg.querySelector('.fixlayer'))svg.insertAdjacentHTML('beforeend',fixLayer(RES));
  const g=svg&&svg.querySelector('.fixlayer');if(g)g.style.display=fixOn?'':'none';
  $('#fixBtn').setAttribute('aria-pressed',String(fixOn));$('#fixNote').hidden=!fixOn;if(fixOn)drawFixNote(RES)}
$('#fixBtn').onclick=()=>setFix(!fixOn);
function zoomToMarker(m){const tf=RES&&RES.svg_tf;if(!tf||m.dxf_x==null)return false;
  const sx=m.dxf_x*tf.scale+tf.off_x,sy=tf.off_y-m.dxf_y*tf.scale,r=stage.getBoundingClientRect();
  const want=Math.max(fitZoom*4,Math.min(fitZoom*14,r.height*0.18/Math.max(m.dxf_r*tf.scale,1e-6)));
  pan.classList.remove('dragging');zoom=clampZ(want);ox=r.width/2-sx*zoom;oy=r.height/2-sy*zoom;apply();showZoom();return true}
$('#finds').addEventListener('click',e=>{const chip=e.target.closest('.mchip');if(!chip)return;
  const n=+chip.dataset.n,m=((RES&&RES.marker_index)||[]).find(x=>x.n===n);if(!m||!zoomToMarker(m))return;
  $$('.mchip.active').forEach(c=>c.classList.remove('active'));chip.classList.add('active');
  if(innerWidth<=980)$('#viewer').scrollIntoView({block:'center'})});

const HIST='cadcheck.history',HIST_MAX=20;
function histAll(){try{return JSON.parse(store.get(HIST))||{}}catch(e){return{}}}
function histGet(file){return histAll()[file]||null}
function histSave(snap){const all=histAll();all[snap.file]=snap;const keys=Object.keys(all);
  if(keys.length>HIST_MAX)keys.sort((a,b)=>all[a].ts-all[b].ts).slice(0,keys.length-HIST_MAX).forEach(k=>delete all[k]);
  store.set(HIST,JSON.stringify(all))}
function snapshot(d){const sc=d.scorecard||{},codes={};(d.findings||[]).forEach(f=>{if(!codes[f.code])codes[f.code]=f.title});
  return {job:d.job,ts:Date.now(),file:d.file||'',score:sc.auto_score??null,max:sc.auto_max??null,percent:sc.percent??null,dq:!!sc.disqualified,codes}}
function ago(ms){const m=Math.floor((Date.now()-ms)/60000);if(m<1)return t('justNow');if(m<60)return m+t('minAgo');if(m<1440)return Math.floor(m/60)+t('hourAgo');return Math.floor(m/1440)+t('dayAgo')}
function codeName(code,fallback){return (CHECK_LABELS[lang]||{})[code]||fallback||code}
function buildDiff(prev,now){const p=Object.keys(prev.codes||{}),n=Object.keys(now.codes||{});
  return {prev,now,fixed:p.filter(c=>!n.includes(c)).map(c=>[c,prev.codes[c]]),added:n.filter(c=>!p.includes(c)).map(c=>[c,now.codes[c]]),stayed:n.filter(c=>p.includes(c)),
    dScore:(prev.percent!=null&&now.percent!=null)?Math.round(now.percent)-Math.round(prev.percent):null}}
const CMP=new Map();
function compareFor(d){if(CMP.has(d.job))return CMP.get(d.job);
  const prev=histGet(d.file),now=snapshot(d),diff=(prev&&prev.job!==d.job)?buildDiff(prev,now):null;
  CMP.set(d.job,diff);histSave(now);
  // 같은 파일을 고쳐서 다시 올린 것 = 재검사. 종류 이름만 보낸다(파일명은 안 보냄).
  if(diff)fetch('/api/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'recheck'})}).catch(()=>{});
  return diff}
function drawCompare(diff){const box=$('#cmp');
  if(!diff){box.innerHTML=`<div class="cmp-hint">${ico('refresh')}<span>${esc(t('cmpFirst'))}</span></div>`;return}
  const {prev,now,fixed,added,stayed,dScore}=diff,pct=v=>v==null?'—':Math.round(v)+'%';
  const delta=dScore==null?'':`<span class="cmp-delta ${dScore>0?'up':dScore<0?'down':''}">${dScore>0?'+':''}${dScore}</span>`;
  const banner=(prev.dq&&!now.dq)?`<div class="cmp-banner good">${esc(t('cmpDqCleared'))}</div>`:(!prev.dq&&now.dq)?`<div class="cmp-banner bad">${esc(t('cmpDqNew'))}</div>`:'';
  const tags=[['fixed',t('cmpFixed'),fixed.length],['stayed',t('cmpStayed'),stayed.length],['added',t('cmpAdded'),added.length]].map(([k,l,n])=>`<span class="cmp-tag ${k}">${esc(l)} <b>${n}</b></span>`).join('');
  const list=(cls,items,icon)=>items.length?`<ul class="cmp-list ${cls}">${items.map(([c,title])=>`<li>${ico(icon)}<span>${esc(codeName(c,title))}</span></li>`).join('')}</ul>`:'';
  const nothing=(!fixed.length&&!added.length)?`<p class="cmp-none">${esc(t('cmpSame'))}</p>`:'';
  box.innerHTML=`<div class="card"><div class="cmp-head"><b>${esc(t('cmpTitle'))}</b><span class="cmp-when">${esc(ago(prev.ts))} · ${esc(t('cmpAgo'))}</span></div>${banner}<div class="cmp-score"><span class="was">${pct(prev.percent)}</span>${ico('arrow')}<span class="now">${pct(now.percent)}</span>${delta}${fixed.length||(prev.dq&&!now.dq)?stk('fixed','pop'):''}</div><div class="cmp-tags">${tags}</div>${list('fixed',fixed,'check')}${list('added',added,'plus')}${nothing}</div>`}

reveal();

applyLang();
loadStats();
if(!store.get('cadcheck.intro'))openGuide(0);
