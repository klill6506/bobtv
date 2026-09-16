from pathlib import Path
import xml.etree.ElementTree as E,json
logos={}
allowed={'svg','g','path','rect','circle','ellipse','polygon','polyline','line','defs','linearGradient','radialGradient','stop','clipPath','title'}
attrs={'viewBox','d','fill','fill-rule','clip-rule','clip-path','id','transform','x','y','x1','y1','x2','y2','width','height','cx','cy','r','rx','ry','points','offset','stop-color','stop-opacity','gradientUnits','gradientTransform','opacity','stroke','stroke-width','xmlns','style'}
for p in Path('web/brands').glob('*.svg'):
 root=E.fromstring(p.read_text())
 def clean(n):
  n.tag=n.tag.split('}')[-1]
  n.attrib={k:v for k,v in n.attrib.items() if k in attrs}
  for child in list(n):
   if child.tag.split('}')[-1] not in allowed:n.remove(child)
   else:clean(child)
 clean(root)
 root.set('xmlns','http://www.w3.org/2000/svg');root.set('class','service-logo');root.set('aria-hidden','true');root.set('focusable','false')
 if 'viewBox' not in root.attrib:root.set('viewBox', '0 0 '+root.attrib['width']+' '+root.attrib['height'])
 root.attrib.pop('width',None);root.attrib.pop('height',None)
 if p.stem in ('itvx','channel4','hbo-max','apple-tv'):root.set('fill','currentColor')
 logos[p.stem]=E.tostring(root,encoding='unicode')
p=Path('web/app.js');s=p.read_text()
if s.startswith('const brandLogos='):s=s.split('\n',1)[1]
s='const brandLogos='+json.dumps(logos)+';\n'+s
old="for(const [i,text] of mark.entries()){const span=document.createElement('span');span.className=i?'caption':'wordmark';span.textContent=text;button.append(span);}"
new="const logo=document.createElement('span');logo.className='logo-wrap';if(brandLogos[id]){const doc=new DOMParser().parseFromString(brandLogos[id],'image/svg+xml');logo.append(document.importNode(doc.documentElement,true));}else{logo.textContent=mark[0];}button.append(logo);const label=document.createElement('span');label.className='service-label';label.textContent=mark[0];button.append(label);"
s=s.replace(old,new);p.write_text(s)
