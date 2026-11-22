/** Decorative isometric house for the overview header. */
export default function HomeDiagram(){
 return <svg className="house" viewBox="0 0 340 130" fill="none" aria-hidden="true">
  <defs><pattern id="mesh" width="24" height="14" patternUnits="userSpaceOnUse"><path d="m0 0 24 14m0-14L0 14" stroke="#30656a" strokeWidth=".6"/></pattern></defs>
  <path d="m5 83 145-82 181 48-143 81z" fill="url(#mesh)"/>
  <g strokeLinejoin="round" stroke="#56adac"><path d="m72 85 77-41 102 40-77 43z" fill="#123641"/>
   <path d="m93 60 66-35 68 30v30l-65 35-69-30z" fill="#173746"/><path d="m93 60 69 30v30l-69-30z" fill="#15484e"/>
   <path d="m86 61 30-44 67-14 52 52-68 36z" fill="#173943"/>
   <path d="m116 17 67-14 52 52-68 36z" fill="#20505a"/><path d="m124 22 54-12 40 40-53 26z" fill="#12333c"/>
   <path d="m138 20 40 50m-24-53 39 46m-24-50 39 43m-74-21 54-15m-43 29 55-20m-44 33 55-24" stroke="#367674"/>
   <path d="m103 69 15 7v12l-15-6zm22 10 13 6v12l-13-6z" fill="#6ad3c2"/>
   <path d="m175 88 13-7v20l-13 7zm20-10 17-9v11l-17 9z" fill="#38787d"/>
  </g><g fill="#78decd"><circle cx="72" cy="85" r="2"/><circle cx="251" cy="84" r="2"/></g>
 </svg>
}
