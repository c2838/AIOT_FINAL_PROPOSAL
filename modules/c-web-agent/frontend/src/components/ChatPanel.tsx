import Icon from './Icon'
import {FormEvent,useEffect,useRef,useState} from 'react'
import {Answer,Filters,System,fromTaipei,label,stamp} from '../types'
import {api,reason} from '../services/api'
const questions=[['室內設備','我房間現在適合開除濕機嗎？'],['外出建議','今天下午去臺中市西區適合嗎？'],['曬衣建議','我現在適合在室內還是戶外曬衣服？']]
const toolNames:Record<string,string>={get_indoor_readings:'室內量測',get_weather_forecast:'行政區預報',get_lifestyle_advice:'生活規則',get_pending_events:'候選事件',get_confirmed_device_state:'設備日誌'}
type Turn={question:string;answer?:Answer;error?:string}
export function ChatPanel({filters,system}:{filters:Filters;system:System|null}){
  const [session]=useState(()=>crypto.randomUUID()),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
  const [turns,setTurns]=useState<Turn[]>([]),lock=useRef(false)
  const log=useRef<HTMLDivElement>(null)
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight},[turns])
  async function send(text:string){
    if(!text.trim()||lock.current)return
    lock.current=true;setBusy(true);setMessage('')
    setTurns(t=>[...t.slice(-15),{question:text}])
    try{const answer=await api<Answer>('/chat','POST',{session_id:session,message:text.trim(),room_id:filters.room,location_id:filters.location.trim()||null,target_time:fromTaipei(filters.time),scenario:filters.scenario})
      setTurns(t=>[...t.slice(0,-1),{question:text,answer}])}
    catch(e){setTurns(t=>[...t.slice(0,-1),{question:text,error:reason(e)}]);setMessage(text)}
    finally{lock.current=false;setBusy(false)}
  }
  function submit(e:FormEvent){e.preventDefault();void send(message)}
  return <section className="panel chat" id="assistant"><div className="section-title"><span className="tile"><Icon name="bot"/></span><div><small className="panel-label">AI 工作區</small><h2>生活建議助理</h2></div><span className="badge model">{system?system.agent_mode==='gemini'?'Gemini 助理':'模板助理':'未連線'}</span></div>
    <div ref={log} className="conversation" aria-live="polite">{!turns.length&&<div className="welcome"><div className="bot-symbol"><Icon name="bot"/></div><h3>想了解哪一種生活情境？</h3><p>選擇下方情境，或直接輸入你的問題。</p></div>}
    {turns.map(({question,answer:a,error},i)=><article key={i}><p className="bubble user">{question}</p>
      {a&&<><div className="reply-meta"><span className={a.data_mode==='mock'?'badge mock':'badge'}>{a.data_mode==='mock'?'模擬資料':'實際來源'}</span> {a.agent_mode==='gemini'?'Gemini 助理':'模板助理'} · {label(a.status)}</div>
      <p className="bubble bot"><b className="answer-label">建議</b>{a.answer}</p>{a.agent_error&&<p className="notice">{a.agent_error}</p>}
      <details open={i===turns.length-1}><summary>資料證據與規則</summary><div className="evidence">
        {a.evidence.map((e,j)=><p key={j}><b>{e.source}</b><br/>{e.detail}<br/><small>{e.at?stamp(e.at):'無確認時間'}{e.until?' 至 '+stamp(e.until):''}</small></p>)}
        {a.rule_ids.length>0&&<p>規則 {a.rule_ids.join('、')} · {a.rule_version}</p>}
        {a.tools_used.length>0&&<p>工具紀錄 · {a.latency_ms} 毫秒<br/>{a.tools_used.map((t,j)=><small key={j} title={t.name}>{toolNames[t.name]??t.name}（{label(t.status)}，{t.latency_ms} 毫秒） </small>)}</p>}
        </div></details>{a.limitations.length>0&&<div className="limitations"><b>限制</b>{a.limitations.map(x=><p key={x}>{x}</p>)}</div>}</>}
      {error&&<p role="alert" className="notice">{error}</p>}</article>)}
      {busy&&<p role="status" className="badge">正在查詢資料與規則…</p>}</div>
    <div className="chat-dock">    <div className="quick">{questions.map(([name,text])=><button disabled={busy} key={name} onClick={()=>send(text)}>{name} ↗</button>)}</div>
<form className="composer" onSubmit={submit}><input aria-label="詢問生活助理" placeholder="輸入問題或補充查詢條件…" maxLength={600} value={message} onChange={e=>setMessage(e.target.value)}/><button className="primary" disabled={busy||!message.trim()}>送出 ↑</button></form></div>
  </section>
}
