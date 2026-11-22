const paths={
 home:'M3 11 12 3l9 8 M5 10v11h14V10 M10 21v-7h4v7',
 temp:'M9 14V6a3 3 0 016 0v8a5 5 0 11-6 0z M12 8v9',
 drop:'M12 2C10 6 4 12 4 15a8 8 0 0016 0c0-4-6-10-8-13z M8 15a4 4 0 003 4',
 signal:'M2 13h5l3-8 4 14 3-8h5',
 bot:'M4 8h16v12H4z M12 8V4 M9 13h.01 M15 13h.01 M9 16h6',
 event:'M3 5h18v12H9l-5 4v-4H3z M7 11h3l2-3 2 6 2-3h2',
 filter:'M3 6h18 M3 12h18 M3 18h18 M8 3v6 M16 9v6 M9 15v6',
 layers:'m3 8 9-5 9 5-9 5z M3 12l9 5 9-5 M3 16l9 5 9-5'
}
export default function Icon({name}:{name:keyof typeof paths}){
 return <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]}/></svg>
}
