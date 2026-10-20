import io, re, html, datetime, textwrap
from urllib.parse import quote
import requests, feedparser, streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import simpleSplit

st.set_page_config(page_title='The Daily Dispatch', page_icon='🗞️', layout='centered')
SECTIONS = [
 ('U.S. & WORLD NEWS','US world top news politics international'),
 ('AVIATION','airlines aviation airports new routes aviation industry'),
 ('TRAVEL','travel destinations tourism rail travel international'),
 ('LAS VEGAS & HENDERSON','Las Vegas Henderson Nevada local news'),
 ('LORAIN COUNTY, OHIO','Lorain OR Vermilion OR Elyria Ohio local news'),
]
COLORS=['#172C4A','#216477','#AA633B','#725B9D','#39735B']
HEADERS={'User-Agent':'DailyDispatchPersonalReader/1.0 (RSS feed reader)'}

def clean(s):
    s=re.sub('<[^>]+>',' ',s or '')
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def get_news(query, count=12):
    url='https://news.google.com/rss/search?q='+quote(query+' when:3d')+'&hl=en-US&gl=US&ceid=US:en'
    r=requests.get(url,headers=HEADERS,timeout=18);r.raise_for_status()
    feed=feedparser.parse(r.content)
    stories=[]; seen=set()
    for e in feed.entries:
        title=clean(e.get('title',''))
        if not title or title.lower() in seen:continue
        seen.add(title.lower())
        source=clean(e.get('source',{}).get('title','')) if e.get('source') else ''
        stories.append({'title':title,'source':source,'url':e.get('link',''),'date':e.get('published',''),'description':clean(e.get('summary',''))})
        if len(stories)>=count:break
    return stories

def weather(lat,lon):
    url='https://api.open-meteo.com/v1/forecast'
    p={'latitude':lat,'longitude':lon,'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code','temperature_unit':'fahrenheit','timezone':'America/Los_Angeles' if lon<-110 else 'America/New_York','forecast_days':5}
    data=requests.get(url,params=p,timeout=15);data.raise_for_status()
    return data.json()['daily']

def write_lines(c,text,x,y,width,font='Helvetica',size=10,leading=15,max_lines=99,color='#263548'):
    c.setFont(font,size);c.setFillColor(HexColor(color))
    lines=simpleSplit(clean(text),font,size,width)
    for line in lines[:max_lines]:
        c.drawString(x,y,line);y-=leading
    return y

def page_header(c,title,date,page,color):
    W,H=612,792
    c.setFillColor(HexColor('#F8FAFC'));c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(HexColor(color));c.rect(0,H-11,W,11,fill=1,stroke=0)
    c.setFillColor(HexColor('#172C4A'));c.setFont('Helvetica-Bold',19);c.drawString(43,746,'THE DAILY DISPATCH')
    c.setFont('Helvetica',9);c.setFillColor(HexColor('#64748B'));c.drawRightString(569,748,date)
    c.setStrokeColor(HexColor('#CDD5DE'));c.line(43,735,569,735)
    c.setFont('Helvetica-Bold',21);c.setFillColor(HexColor(color));c.drawString(43,699,title)
    c.setFont('Helvetica',8);c.setFillColor(HexColor('#6B7280'));c.drawString(43,29,'Fresh headlines • Source links included • Generated on demand')
    c.drawRightString(569,29,str(page))

def story(c,story,x,y,width,accent,large=False):
    if y<100:return y
    size=15 if large else 12
    y=write_lines(c,story['title'],x,y,width,'Helvetica-Bold',size,19 if large else 16,3,'#14253A')-5
    src=story['source'] or 'News source'
    y=write_lines(c,src,x,y,width,'Helvetica-Bold',8,11,1,accent)-4
    # Only source-provided summaries; do not fabricate article copy.
    desc=story.get('description','')
    if desc and clean(desc)!=clean(story['title']):
        y=write_lines(c,desc,x,y,width,'Helvetica',9,13,3)-5
    if story['url']:
        c.setFillColor(HexColor(accent));c.setFont('Helvetica',8)
        c.drawString(x,y,'Read original article ↗'.replace('↗','>'))
        c.linkURL(story['url'],(x,y-3,x+125,y+12),relative=0)
        y-=16
    c.setStrokeColor(HexColor('#DEE4EC'));c.line(x,y,x+width,y)
    return y-19

def news_page(c,title,items,date,page,color):
    page_header(c,title,date,page,color)
    if not items:
        write_lines(c,'No current stories were returned for this section. Try generating again later.',43,644,510)
    else:
        colwidth=247
        for i,s in enumerate(items[:10]):
            col=i//5; pos=i%5
            x=43+col*279
            # Fixed item slots keep every headline readable and pages clean.
            y=651-pos*119
            story(c,s,x,y,colwidth,color,large=(pos==0))
    c.showPage()

def build_pdf(news,forecasts,stamp):
    buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=(612,792))
    c.setTitle('The Daily Dispatch — '+stamp)
    front=[]
    for title,_ in SECTIONS:
        if news.get(title):front.append((title,news[title][0]))
    page_header(c,'TODAY AT A GLANCE',stamp,1,'#172C4A')
    c.setFillColor(HexColor('#E8F2F6'));c.roundRect(43,511,526,150,12,fill=1,stroke=0)
    c.setFillColor(HexColor('#216477'));c.setFont('Helvetica-Bold',10);c.drawString(60,635,'LEAD STORY')
    if front:
        write_lines(c,front[0][1]['title'],60,607,490,'Helvetica-Bold',19,25,3)
        write_lines(c,front[0][1]['source'],60,537,490,'Helvetica',10,12,1)
    for i,(section,s) in enumerate(front[1:5]):
        x=43+(i%2)*270;y=466-(i//2)*195
        c.setFillColor(HexColor(COLORS[(i+1)%len(COLORS)]));c.roundRect(x,y+9,247,6,3,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',10);c.drawString(x,y-13,section)
        write_lines(c,s['title'],x,y-40,245,'Helvetica-Bold',13,18,4)
        if s['url']:c.linkURL(s['url'],(x,y-110,x+247,y),relative=0)
    c.showPage()
    for i,(section,_) in enumerate(SECTIONS):news_page(c,section,news.get(section,[]),stamp,i+2,COLORS[i])
    page_header(c,'WEATHER: NEVADA & OHIO',stamp,7,'#216477')
    y=652
    for city,d in forecasts.items():
        c.setFillColor(HexColor('#172C4A'));c.setFont('Helvetica-Bold',17);c.drawString(43,y,city);y-=30
        if not d:
            y=write_lines(c,'Forecast temporarily unavailable.',43,y,500)-32;continue
        for i,day in enumerate(d['time']):
            if i>=5:break
            hi=round(d['temperature_2m_max'][i]);lo=round(d['temperature_2m_min'][i]);rain=d['precipitation_probability_max'][i]
            c.setFillColor(HexColor('#F0F5F9' if i%2==0 else '#FFFFFF'));c.rect(43,y-11,526,28,fill=1,stroke=0)
            c.setFillColor(HexColor('#24344A'));c.setFont('Helvetica',10)
            c.drawString(54,y,day);c.drawString(210,y,f'High {hi}°F   Low {lo}°F');c.drawString(430,y,f'Rain {rain}%');y-=31
        y-=39
    c.setFillColor(HexColor('#64748B'));c.setFont('Helvetica',8);c.drawString(43,80,'Forecast data: Open-Meteo.com. Check local alerts and official forecasts for safety.')
    c.showPage();c.save();buf.seek(0);return buf.getvalue()

st.markdown('<h1 style="margin-bottom:0">🗞️ The Daily Dispatch</h1>',unsafe_allow_html=True)
st.caption('Your on-demand personal newspaper • Modern edition • 7 printable pages')
st.info('Sections: U.S. & World · Aviation · Travel · Las Vegas & Henderson · Lorain County, Ohio · Weather')
if 'pdf' not in st.session_state:st.session_state.pdf=None
if st.button('📰 Generate Today’s Edition',type='primary',use_container_width=True):
    news={};errors=[]
    with st.spinner('Gathering current headlines and weather…'):
        for section,query in SECTIONS:
            try:news[section]=get_news(query)
            except Exception as exc:news[section]=[];errors.append(section)
        forecasts={}
        for city,lat,lon in [('Las Vegas / Henderson',36.17,-115.14),('Lorain County, Ohio',41.45,-82.18)]:
            try:forecasts[city]=weather(lat,lon)
            except Exception:forecasts[city]=None;errors.append(city+' weather')
        now=datetime.datetime.now().astimezone()
        stamp=now.strftime('%A, %B %d, %Y')
        st.session_state.pdf=build_pdf(news,forecasts,stamp)
        st.session_state.filename='Daily_Dispatch_'+now.strftime('%Y-%m-%d')+'.pdf'
        st.session_state.totals={k:len(v) for k,v in news.items()}
        st.session_state.errors=errors
if st.session_state.pdf:
    st.success('Your seven-page edition is ready!')
    st.download_button('⬇️ Download / Print Newspaper (PDF)',st.session_state.pdf,file_name=st.session_state.filename,mime='application/pdf',type='primary',use_container_width=True)
    for k,v in st.session_state.totals.items():st.caption(f'{k}: {v} fresh headlines')
    if st.session_state.errors:st.warning('Some feeds could not be reached: '+', '.join(st.session_state.errors)+'. Their pages may be sparse. Try again later.')
st.caption('Headlines and feed excerpts are attributed to publishers, with clickable links to full stories. No full articles are copied. Requires an internet connection.')
