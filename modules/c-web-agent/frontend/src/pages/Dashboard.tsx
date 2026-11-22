import {useEffect,useState} from 'react'
import {api,query,reason} from '../services/api'
import {Candidate,Filters,Reading,Scenario,System,label,stamp} from '../types'
import HomeDiagram from '../components/HomeDiagram'
import Icon from '../components/Icon'
import {Trend} from '../components/Trend'
import {ChatPanel} from '../components/ChatPanel'
import {Events} from '../components/Events'

const rooms=[['room-01','客廳'],['room-02','臥室']]
export default function Dashboard(){
  const [f,set]=useState<Filters>({room:'room-01',location:'',time:'',scenario:'normal'})
  const [seq,bump]=useState(0),[sys,setSys]=useState<System|null>(null),[indoor,setIndoor]=useState<Reading|null>(null)
  const [rows,setRows]=useState<Reading[]>([]),[events,setEvents]=useState<Candidate[]>([]),[errors,setErrors]=useState<string[]>([])
  const [loading,setLoading]=useState(true),[eventErr,setEventErr]=useState('')
  const [updated,setUpdated]=useState<string|null>(null)
  useEffect(()=>{
    let alive=true
    async function load(){
      setLoading(true);setErrors([]);setIndoor(null);setRows([]);setEvents([]);setEventErr('')
      const system=await api<System>('/system/status').catch(()=>null)
      if(!alive)return
      setSys(system)
      if(!system){setErrors(['無法連線至後端，請啟動服務後重新整理。']);setLoading(false);return}
      const filter=query({room_id:f.room,scenario:system.data_mode==='mock'?f.scenario:'normal'})
      const [a,b,c]=await Promise.allSettled([api<Reading>('/indoor/latest?'+filter),api<Reading[]>('/indoor/history?'+filter),api<Candidate[]>('/events?'+query({room_id:f.room}))])
      if(!alive)return
      setIndoor(a.status==='fulfilled'?a.value:null);setRows(b.status==='fulfilled'?b.value:[])
      setEvents(c.status==='fulfilled'?c.value:[]);setEventErr(c.status==='rejected'?reason(c.reason):'')
      if([a,b,c].some(result=>result.status==='fulfilled'))setUpdated(new Date().toISOString())
      setErrors([a,b].flatMap(x=>x.status==='rejected'?[reason(x.reason)]:[]));setLoading(false)
    }
    void load();return ()=>{alive=false}
  },[seq,f.room,f.scenario])
  function update<K extends keyof Filters>(key:K,value:Filters[K]){set(prev=>({...prev,[key]:value}))}
  const room=rooms.find(([id])=>id===f.room)?.[1]??f.room
  return <><header className="navbar"><div className="nav-inner"><div className="brand"><span className="brandmark"><Icon name="home"/></span>居家環境觀測站</div>
    <nav aria-label="主導覽"><a href="#overview">環境總覽</a><a href="#assistant">生活建議</a><a href="#events">事件回饋</a></nav>
    <div className="nav-status"><span className="online"><i className={sys?'dot':'dot off'}/>{sys?'系統已連線':loading?'連線中':'系統離線'}</span><span className={'badge '+(sys?.data_mode==='mock'?'mock':'')}>{sys?.data_mode==='mock'?'模擬資料':sys?'實際來源':'來源未知'}</span><span className="badge model">{sys?.agent_mode==='gemini'?'Gemini 助理':sys?'模板助理':'未連線'}</span></div></div></header>
    <main><section className="hero"><div className="hero-copy"><p className="kicker"><Icon name="signal"/> 環境總覽</p><h1>智慧居家環境中控台</h1><p>整合室內感測、天氣預報與 AI 建議的生活儀表板</p></div><HomeDiagram/>
    <div className="sync"><small>最後資料更新 · 臺灣時間</small><time>{updated?stamp(updated):'—'}</time><button disabled={loading} onClick={()=>bump(n=>n+1)}>↻　更新資料</button></div></section>
    <section id="overview" aria-label="室內環境" className="monitor">
    {(['temperature_c','relative_humidity_pct'] as const).map((k,i)=><article key={k} className={'card metric metric-'+i}><div className="metric-title"><span className="tile"><Icon name={i?'drop':'temp'}/></span><h2>{i?'相對濕度':'室內溫度'}</h2></div>
    <p className="reading">{indoor?.[k]??'—'}<small>{i?'%':'°C'}</small></p><div className="metric-foot"><b>{room}</b><span>{indoor?.device_id??'等待量測'}</span></div></article>)}
    <Trend rows={rows}/></section>
    <div className="telemetry"><span><Icon name="signal"/>最近量測 <b>{stamp(indoor?.measured_at??null)}</b></span><span>品質 <b className={indoor?.quality_flag==='ok'?'good':'warn'}>{indoor?label(indoor.quality_flag):'無資料'}</b></span><span>時效 <b className={indoor&&!indoor.is_stale?'good':'warn'}>{indoor?(indoor.is_stale?'已過期':'新鮮'):'未知'}</b></span>{sys?.data_mode==='mock'&&<small>量測、預報與事件均為模擬資料</small>}</div>
    {errors.map((err,i)=><p role="alert" className="notice" key={i}>{err}</p>)}
    <section className="filters"><h2 className="filter-title"><Icon name="filter"/>查詢條件</h2><label>查詢房間<select value={f.room} onChange={e=>update('room',e.target.value)}>{rooms.map(([id,n])=><option key={id} value={id}>{n} · {id}</option>)}</select></label>
    <label>外出／曬衣行政區<input placeholder="例：臺中市西區" maxLength={100} value={f.location} onChange={e=>update('location',e.target.value)}/></label>
    <label>目標時間（臺灣）<input type="datetime-local" value={f.time} onChange={e=>update('time',e.target.value)}/></label>
    {sys?.data_mode==='mock'&&<label>模擬情境<select value={f.scenario} onChange={e=>update('scenario',e.target.value as Scenario)}>{Object.entries({normal:'正常量測',offline:'感測中斷',missing:'讀值缺漏',stale:'量測過期',invalid:'讀值超界',weather_error:'氣象來源失敗'}).map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>}</section>
    <div className="workbench"><ChatPanel key={[f.room,f.scenario,sys?.data_mode].join('/')} filters={f} system={sys}/><Events items={events} error={eventErr}/></div>
    <footer>居家環境與外出建議代理人<span>顯示時間採臺灣時間（UTC+8）</span></footer></main></>
}
