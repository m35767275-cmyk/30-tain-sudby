"""Creates personalized astrological entertainment PDF using unmodified original content."""
from pathlib import Path
import re,json,io
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

ROOT=Path(__file__).resolve().parents
SIGNS=['Овен','Телец','Близнецы','Рак','Лев','Дева','Весы','Скорпион','Стрелец','Козерог','Водолей','Рыбы']
SOURCE=(ROOT/'texts/30_tain_personalizaciya.md').read_text(encoding='utf-8')
COMPAT={(x['sign_1'],x['sign_2']):x for x in json.loads((ROOT/'texts/compatibility_12x12.json').read_text(encoding='utf-8'))}
CHAPTERS=[]
for number,title,body in re.findall(r'^## Тайна (\d+)\. ([^\n]+)\n(.*?)(?=^## Тайна \d+\.|\Z)',SOURCE,re.M|re.S):
    choices={}
    for ans,section in re.findall(r'^### Ответ: ([^\n]+)\n(.*?)(?=^### Ответ: |\Z)',body,re.M|re.S):
        prose=section.split('**Шёпот оракула:**')[0].strip()
        choices[ans.strip()]=' '.join(prose.split())
    CHAPTERS.append({'number':int(number),'title':title.strip(),'choices':choices})
assert len(CHAPTERS)==30 and sum(len(c['choices']) for c in CHAPTERS)==131
assert len(COMPAT)==144

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('Oracle',FONT))
pdfmetrics.registerFont(TTFont('OracleBold',FONT_BOLD))
PAPER=colors.HexColor('#171126'); GOLD=colors.HexColor('#CDAA69'); LIGHT=colors.HexColor('#28213D')
styles={
 'heading':ParagraphStyle('OracleHeading',fontName='OracleBold',fontSize=19,leading=26,textColor=GOLD,spaceAfter=17),
 'sub':ParagraphStyle('OracleSub',fontName='OracleBold',fontSize=11.7,leading=17,textColor=GOLD,spaceBefore=9,spaceAfter=9),
 'text':ParagraphStyle('OracleText',fontName='Oracle',fontSize=10,leading=16,textColor=colors.HexColor('#292039'),spaceAfter=12),
 'note':ParagraphStyle('OracleNote',fontName='Oracle',fontSize=8.5,leading=13,textColor=colors.HexColor('#73677E')),
 'center':ParagraphStyle('OracleCenter',fontName='OracleBold',fontSize=26,leading=35,textColor=GOLD,alignment=TA_CENTER,spaceAfter=15),
 'center2':ParagraphStyle('OracleCenter2',fontName='Oracle',fontSize=12,leading=19,textColor=colors.HexColor('#59486A'),alignment=TA_CENTER,spaceAfter=17)
}

def paragraph(t,style='text'):
    return Paragraph(escape(str(t)),styles[style])

def illustration(sign,maxw=200,maxh=205):
    if sign not in SIGNS: return None
    file=next((ROOT/'illustrations').glob(f'*_{sign}.svg'),None)
    if not file: return None
    try:
        d=svg2rlg(str(file))
        scale=min(maxw/d.width,maxh/d.height)
        d.scale(scale,scale)
        d.width*=scale;d.height*=scale
        return d
    except Exception: return None

def make_pdf(answers,partner_sign=None,order_id='PREVIEW'):
    """answers = list of 30 exact selections, partner_sign optional for directed match."""
    if not isinstance(answers,list) or len(answers)!=30:raise ValueError('Нужны ровно 30 ответов')
    for i,val in enumerate(answers):
        if not isinstance(val,str) or val not in CHAPTERS[i]['choices']:raise ValueError(f'Неверный ответ #{i+1}')
    sign=answers[2]; sign=sign if sign in SIGNS else None
    if partner_sign and partner_sign not in SIGNS:raise ValueError('Неизвестный знак партнёра')
    out=io.BytesIO()
    def footer(c,doc):
        c.saveState(); w,h=A4
        c.setStrokeColor(GOLD);c.line(38,38,w-38,38)
        c.setFont('Oracle',8);c.setFillColor(colors.HexColor('#756981'))
        c.drawString(42,26,'30 ТАЙН СУДЬБЫ  •  художественная интерпретация')
        c.drawRightString(w-42,26,str(doc.page));c.restoreState()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=47,leftMargin=47,topMargin=51,bottomMargin=54,title='30 тайн судьбы — персональный отчёт',author='30 тайн судьбы')
    story=[Spacer(1,55),paragraph('30 ТАЙН СУДЬБЫ','center'),paragraph('Твоя мистическая книга любви','center2')]
    if sign:
        drawing=illustration(sign,230,240)
        if drawing:story.extend([drawing,Spacer(1,18)])
    story.extend([paragraph('Персональный символический портрет','center2'),paragraph(f'Номер отчёта: {order_id}','note'),Spacer(1,28),paragraph('Над ночным небом загораются созвездия. Тридцать ответов стали тридцатью ключами — не к неизбежному будущему, а к твоим чувствам, мечтам и возможностям.'),paragraph('Этот художественный материал создан по твоим ответам. Астрология здесь используется как символический язык, а не как научный метод предсказания.' ,'note'),PageBreak()])
    for i,c in enumerate(CHAPTERS):
        block=[paragraph(f'Тайна {i+1}. {c["title"]}','heading')]
        if i==2 and sign:
            d=illustration(sign,125,125)
            if d:block.append(d)
        block.extend([paragraph(f'Твой ответ: {answers[i]}','sub'),paragraph(c['choices'][answers[i]]),paragraph('Шёпот оракула: Пусть свет звёзд помогает увидеть себя яснее, а решения остаются за тобой.','note'),Spacer(1,15)])
        story.append(KeepTogether(block))
    story.append(PageBreak())
    story.extend([paragraph('Созвездия двух сердец','heading')])
    if sign and partner_sign:
        story.extend([paragraph(f'{sign} и {partner_sign}','sub')])
        d=illustration(partner_sign,160,150)
        if d:story.append(d)
        story.append(paragraph(COMPAT[(sign,partner_sign)]['text']))
    elif sign:
        story.extend([paragraph(f'Твой знак: {sign}','sub'),paragraph('Знак другого человека не указан. Символическая совместимость доступна для всех 12 знаков: выбери знак партнёра при оформлении, чтобы увидеть одно из 144 направленных сочетаний.')])
    else:story.append(paragraph('Твой знак не указан. Для раздела о совместимости выбери знак зодиака и, при желании, знак партнёра.'))
    story.extend([Spacer(1,20),paragraph('Эпилог: письмо из будущего','heading'),paragraph('Пусть эта книга напоминает: у твоей истории нет заранее написанного финала. Прислушивайся к себе, замечай поступки других людей и выбирай отношения, где есть уважение, доверие и свобода.'),paragraph('18+. Развлекательный символический прогноз. Он не раскрывает чужие мысли, не предсказывает достоверно будущее и не заменяет профессиональную консультацию.','note')])
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

if __name__=='__main__':
    a=[next(iter(c['choices'])) for c in CHAPTERS];a[2]='Весы'
    (ROOT/'examples/sample_personalized.pdf').write_bytes(make_pdf(a,'Овен','DEMO-001'))
    print('Generated sample', len(CHAPTERS),sum(len(c['choices']) for c in CHAPTERS),len(COMPAT))
