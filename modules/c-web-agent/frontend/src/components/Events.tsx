import Icon from './Icon'
import {useEffect,useRef,useState} from 'react'
import {api,query,reason} from '../services/api'
import {Candidate,Feedback,fromTaipei,toInput,label,stamp} from '../types'
function EventCard({item:e}:{item:Candidate}){
  const [rows,setRows]=useState<Feedback[]>([]),[selected,select]=useState(''),[versions,setVersions]=useState<Feedback[]>([])
  const [choice,setChoice]=useState(''),[time,setTime]=useState(''),[busy,setBusy]=useState(true),[err,setErr]=useState('')
  const [ready,setReady]=useState(false)
  const attempt=useRef<object|null>(null),lock=useRef(false)
  const replyAttempt=useRef<{key:string;repliedAt:string}|null>(null)
  const current=rows.find(r=>r.feedback_id===selected)
  async function refresh(fid?:string){
    const list=await api<Feedback[]>('/feedback?'+query({event_id:e.event_id}))
    const id=fid||selected||list[0]?.feedback_id||''
    const history=id?await api<Feedback[]>('/feedback/'+encodeURIComponent(id)+'/history'):[]
    setRows(list);select(id);setVersions(history);setReady(true)
    const row=list.find(r=>r.feedback_id===id)
    setChoice(row?.status==='uncertain'?'uncertain':row?.operation_label||'');setTime(toInput(row?.operation_at||null))
  }
  async function task(action:()=>Promise<void>){
    if(lock.current)return
    lock.current=true;setBusy(true);setErr('')
    try{await action()}catch(ex){setErr(reason(ex))}finally{setBusy(false);lock.current=false}
  }
  useEffect(()=>{void task(()=>refresh())},[e.event_id])
  async function ask(){
    const t=Date.now()
    attempt.current??={feedback_id:crypto.randomUUID(),event_id:e.event_id,asked_at:new Date(t).toISOString(),expires_at:new Date(t+15*60000).toISOString()}
    const saved=await api<Feedback>('/feedback','POST',attempt.current)
    await refresh(saved.feedback_id);attempt.current=null
  }
  async function save(){
    if(!current||!choice)return
    const key=JSON.stringify([selected,current.feedback_version,choice,time])
    if(replyAttempt.current?.key!==key)replyAttempt.current={key,repliedAt:new Date().toISOString()}
    const saved=await api<Feedback>('/feedback/'+encodeURIComponent(selected),'PUT',{feedback_version:current.feedback_version,
      status:choice==='uncertain'?'uncertain':'confirmed',replied_at:replyAttempt.current.repliedAt,
      operation_label:choice==='uncertain'?null:choice,operation_at:['none','uncertain'].includes(choice)?null:fromTaipei(time)})
    await refresh(saved.feedback_id);replyAttempt.current=null
  }
  return <article className="event-card"><div className="between"><code>{e.event_id}</code><span className={"badge state-"+(current?.status??"pending")}>{current?label(current.status):'候選事件'}</span></div>
    <h3>室內溫濕度變化</h3><p className="muted">{stamp(e.start_at)} 至 {e.end_at?stamp(e.end_at):'尚未結束'}<br/>偵測 {stamp(e.detected_at)} · 事件第 {e.event_version} 版 · {label(e.quality_flag)}</p>
    <div className="event-values"><span>溫度變化 <b>{String(e.features.temperature_delta_c??'—')} °C</b></span><span>濕度變化 <b>{String(e.features.relative_humidity_delta_pct_points??'—')} 百分點</b></span></div>
    {current&&<><label>已儲存詢問<select value={selected} disabled={busy} onChange={ev=>task(()=>refresh(ev.target.value))}>{rows.map(r=><option key={r.feedback_id} value={r.feedback_id}>{stamp(r.asked_at)} · {label(r.status)} · 第 {r.feedback_version} 版</option>)}</select></label>
      <p className="muted">回覆期限 {stamp(current.expires_at)}</p><fieldset disabled={busy}><legend>當時有操作設備嗎？</legend>
      <div className="choices">{['ac','dehumidifier','window','mixed','none','other','uncertain'].map(k=><button type="button" key={k} aria-pressed={choice===k} className={choice===k?'chosen':''} onClick={()=>setChoice(k)}>{label(k)}</button>)}</div>
      <label>實際操作時間（可略）<input type="datetime-local" disabled={['uncertain','none'].includes(choice)} value={time} onChange={ev=>setTime(ev.target.value)}/></label>
      <button className="primary wide" disabled={!choice} onClick={()=>task(save)}>{['confirmed','uncertain'].includes(current.status)?'儲存更正':'送出回覆'}</button></fieldset>
      <details><summary>查閱版本紀錄（{versions.length}）</summary>{versions.map(v=><p key={v.feedback_version}>第 {v.feedback_version} 版 · {label(v.status)} {v.operation_label?label(v.operation_label):''}<br/><small>{stamp(v.updated_at)}{v.operation_at?' · 操作 '+stamp(v.operation_at):''}</small></p>)}</details></>}
    <div className="actions"><button disabled={busy||!ready} onClick={()=>task(ask)}>{current?'新增詢問':'開始詢問'}</button><button disabled={busy} onClick={()=>task(()=>refresh())}>重新查詢</button></div>
    {err&&<p role="alert" className="notice">{err}</p>}</article>
}
export function Events({items,error}:{items:Candidate[];error:string}){
  return <section className="panel" id="events"><div className="section-title"><span className="tile amber"><Icon name="event"/></span><div><small className="panel-label">事件監測</small><h2>事件詢問與回饋</h2></div><span className="event-count">{items.length}</span></div>
  <p className="muted">候選事件需要人工確認操作。</p>{error&&<p className="notice">{error}</p>}{items.map(e=><EventCard key={e.event_id} item={e}/>)}{!items.length&&!error&&<p>此房間目前沒有候選事件。</p>}</section>
}
