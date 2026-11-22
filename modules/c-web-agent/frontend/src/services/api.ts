export class ApiError extends Error { constructor(public status:number,message:string){super(message)} }
const base=window.location.port==='8000'?'/api':'http://127.0.0.1:8000/api'
export async function api<T>(path:string,method='GET',data?:unknown):Promise<T>{
  let res:Response
  try {res=await fetch(base+path,{method,headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined,signal:AbortSignal.timeout(path==='/chat'?150000:20000)})}
  catch {throw new Error('無法連線至後端，請確認服務已啟動。')}
  const body=await res.json()
  if(!res.ok)throw new ApiError(res.status,body.error?.message??'資料讀取失敗。')
  return body as T
}
export const reason=(e:unknown)=>e instanceof Error?e.message:'讀取失敗，請重試。'
export const query=(entries:Record<string,string>)=>new URLSearchParams(entries).toString()
