import {useEffect,useRef,useState} from 'react'
import {Reading,stamp} from '../types'
const series=[{key:'temperature_c',unit:'°C',color:'#43dfc0'},{key:'relative_humidity_pct',unit:'%',color:'#75aaff'}] as const
export function Trend({rows}:{rows:Reading[]}){
 const box=useRef<HTMLDivElement>(null),[width,size]=useState(500),[focus,setFocus]=useState<number|null>(null)
 useEffect(()=>{if(!box.current)return;const obs=new ResizeObserver(([entry])=>size(Math.max(120,entry.contentRect.width)));obs.observe(box.current);return ()=>obs.disconnect()},[])
 const start=Date.parse(rows[0]?.measured_at),end=Date.parse(rows.at(-1)?.measured_at??'')
 const left=35,right=width-12
 const x=(r:Reading)=>left+(Date.parse(r.measured_at)-start)/Math.max(1,end-start)*(right-left)
 const selected=focus!==null?rows[Math.min(focus,rows.length-1)]:null
 const valid=rows.some(r=>r.quality_flag==='ok'&&series.some(s=>r[s.key]!=null))
 return <section className="trend card"><div className="chart-head"><h2>環境變化趨勢</h2><span className="legend"><i/>溫度 °C <i/>濕度 %</span></div><div className="plot" ref={box}>
 {valid?<><svg width="100%" height="118" role="img" aria-label="近期量測，溫度與濕度上下分軸。左右鍵查看讀值" tabIndex={0}
 onBlur={()=>setFocus(null)} onPointerLeave={()=>setFocus(null)} onKeyDown={e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();setFocus(Math.min(rows.length-1,Math.max(0,(focus??0)+(e.key==='ArrowRight'?1:-1))))}}}
 onPointerMove={e=>{const px=e.clientX-e.currentTarget.getBoundingClientRect().left;setFocus(rows.reduce((best,r,i)=>Math.abs(x(r)-px)<Math.abs(x(rows[best])-px)?i:best,0))}}>
 {series.map(({key,color},lane)=>{const vals=rows.flatMap(r=>r.quality_flag==='ok'&&r[key]!=null?[r[key] as number]:[]);if(!vals.length)return null
 const lo=Math.floor(Math.min(...vals)),hi=Math.max(lo+1,Math.ceil(Math.max(...vals))),top=lane*58+8
 let prev=0
 const d=rows.map(r=>{const v=r[key],t=Date.parse(r.measured_at);if(r.quality_flag!=='ok'||v==null){prev=0;return ''}
 const cmd=!prev||t-prev>300000?'M':'L';prev=t;return cmd+x(r)+' '+(top+42-42*(v-lo)/(hi-lo))}).join(' ')
 return <g key={key}>{[hi,lo].map((v,i)=><g key={i}><text x="0" y={top+42*i+4} fill="#a9bacb" fontSize="10">{v}</text><path d={`M${left} ${top+i*42}H${right}`} stroke="#324255" strokeDasharray="3 5"/></g>)}<path d={d} stroke={color} fill="none" strokeLinejoin="round" strokeWidth="2"/></g>})}
 {selected&&<path d={`M${x(selected)} 0v118`} stroke="#adc0cf" strokeDasharray="3 3"/>}</svg>
 {selected&&<output className="chart-tip" style={{[x(selected)>width/2?'left':'right']:4}}>{stamp(selected.measured_at)}<br/>{selected.temperature_c??'—'} °C · {selected.relative_humidity_pct??'—'} % · {selected.quality_flag==='ok'?'有效':'品質異常'}</output>}
 <div className="between axis"><span>{stamp(rows[0].measured_at)}</span><span>{stamp(rows[rows.length-1].measured_at)}</span></div></>:<p className="chart-empty">目前沒有有效量測可繪圖</p>}</div></section>
}
