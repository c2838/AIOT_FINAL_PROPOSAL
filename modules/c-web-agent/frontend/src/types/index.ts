export type Scenario = 'normal'|'stale'|'missing'|'invalid'|'offline'|'weather_error'
export interface System {data_mode:'mock'|'real';agent_mode:'gemini'|'template';model:string|null}
export interface Reading {temperature_c:number|null;relative_humidity_pct:number|null;measured_at:string;quality_flag:string;is_stale:boolean;device_id:string;room_id:string}
export interface Candidate {event_id:string;room_id:string;start_at:string;end_at:string|null;detected_at:string;features:Record<string,unknown>;quality_flag:string;event_version:number}
export interface Feedback {feedback_id:string;event_id:string;asked_at:string;expires_at:string;replied_at:string|null;operation_at:string|null;operation_label:string|null;status:string;feedback_version:number;updated_at:string}
export interface Evidence {source:string;detail:string;at:string|null;until:string|null}
export interface Answer {intent:string;status:string;answer:string;evidence:Evidence[];limitations:string[];tools_used:{name:string;status:string;latency_ms:number}[];rule_ids:string[];rule_version:string|null;data_mode:'mock'|'real';agent_mode:'template'|'gemini';agent_error:string|null;latency_ms:number}
export interface Filters {room:string;location:string;time:string;scenario:Scenario}
export const names:Record<string,string>={ok:'有效',missing:'缺值',invalid_range:'超出範圍',invalid:'資料異常',stale:'已過期',upstream_error:'來源失敗',clarify:'待補充',pending:'待回覆',confirmed:'已確認',uncertain:'不確定',expired:'已逾時',gap:'資料缺口',ac:'冷氣',dehumidifier:'除濕機',window:'開窗',mixed:'混合操作',none:'明確無操作',other:'其他'}
export const label=(key:string)=>names[key]??key
export const stamp=(s:string|null)=>s?new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(s)):'—'
export const fromTaipei=(s:string)=>s?new Date(s+(s.length===16?':00':'')+'+08:00').toISOString():null
export const toInput=(s:string|null)=>s?new Date(new Date(s).getTime()+8*3600000).toISOString().slice(0,16):''
