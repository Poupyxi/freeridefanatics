class UciIconicTour extends HTMLElement {
  connectedCallback(){
    if(this.shadowRoot) return;
    const root = this.attachShadow({mode:'open'});
    root.innerHTML = `<style>:host{display:block;overflow-x:auto;overflow-y:hidden;color:#20231f;--paper:#f5f4f0;--ink:#20231f;--ghost:#6f756f;--accent:#8aa377}
    *{box-sizing:border-box}
    .tour{width:max(1440px,100%);height:300px;min-height:250px;display:grid;grid-template-columns:repeat(9,1fr);position:relative;overflow:hidden;background:var(--paper);isolation:isolate}
    .tour:after{content:"";position:absolute;inset:0;z-index:5;pointer-events:none;opacity:.035;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
    .stage{position:relative;min-width:0;overflow:hidden;cursor:pointer;transition:background .4s ease}
    .stage{transition:opacity .4s ease}
    .head{position:absolute;z-index:3;top:14px;left:34px;right:26px}.number{font-size:10px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--accent)}
    h2{margin:9px 0 4px;font:500 clamp(26px,2.4vw,43px)/.96 Georgia,serif;letter-spacing:-.04em}.meta{font-size:10px;letter-spacing:.16em;text-transform:uppercase;opacity:.48}
    svg{position:absolute;left:0;bottom:-24px;width:100%;height:76%;overflow:visible}.ghost,.draw{fill:none;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}.ghost{stroke:var(--ghost);stroke-width:3.2;opacity:.48}.stage .ghost.detail{opacity:.22}.draw{stroke:var(--ink);stroke-width:3.35;stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset 1.5s cubic-bezier(.65,0,.2,1)}.draw.detail{stroke-width:2.5;transition-delay:.22s}.draw.accent{stroke:var(--accent);stroke-width:3.6;transition-delay:.45s}.s1 .ghost,.s1 .draw{filter:url(#rough1)}.s2 .ghost,.s2 .draw{filter:url(#rough2)}.s3 .ghost,.s3 .draw{filter:url(#rough3)}.s4 .ghost,.s4 .draw{filter:url(#rough4)}.s5 .ghost,.s5 .draw{filter:url(#rough5)}.s6 .ghost,.s6 .draw{filter:url(#rough6)}.connector{z-index:2;pointer-events:none}.connector .ghost{stroke-width:3.35;opacity:.58;filter:url(#roughMain)}.hover-line{fill:none;stroke:var(--ink);stroke-width:3.35;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1;filter:url(#roughMain);transition:stroke-dashoffset 1.25s cubic-bezier(.65,0,.2,1)}.tour:has(section:nth-of-type(1):hover) .hover-1,.tour:has(section:nth-of-type(1).active) .hover-1,.tour:has(section:nth-of-type(2):hover) .hover-2,.tour:has(section:nth-of-type(2).active) .hover-2,.tour:has(section:nth-of-type(3):hover) .hover-3,.tour:has(section:nth-of-type(3).active) .hover-3,.tour:has(section:nth-of-type(4):hover) .hover-4,.tour:has(section:nth-of-type(4).active) .hover-4,.tour:has(section:nth-of-type(5):hover) .hover-5,.tour:has(section:nth-of-type(5).active) .hover-5,.tour:has(section:nth-of-type(6):hover) .hover-6,.tour:has(section:nth-of-type(6).active) .hover-6{stroke-dashoffset:0}.shade{stroke:none;fill:var(--ink);opacity:0;transition:opacity .55s .35s ease}.stage:hover .shade,.stage.active .shade{opacity:.15}.hatch{fill:none;stroke:var(--ink);stroke-width:1.7;opacity:0;stroke-linecap:round;transition:opacity .55s .5s ease}.stage:hover .hatch,.stage.active .hatch{opacity:.34}
    .stage:hover .draw,.stage.active .draw{stroke-dashoffset:0}
    .s7 .ghost,.s7 .draw{filter:url(#rough7)}.s8 .ghost,.s8 .draw{filter:url(#rough8)}.s9 .ghost,.s9 .draw{filter:url(#rough9)}
    .tour:has(section:nth-of-type(7):hover) .hover-7,.tour:has(section:nth-of-type(7).active) .hover-7,.tour:has(section:nth-of-type(8):hover) .hover-8,.tour:has(section:nth-of-type(8).active) .hover-8,.tour:has(section:nth-of-type(9):hover) .hover-9,.tour:has(section:nth-of-type(9).active) .hover-9{stroke-dashoffset:0}
    .stage button{position:absolute;z-index:4;inset:0;width:100%;border:0;background:transparent;cursor:inherit}
    @media(min-width:821px) and (max-width:1500px){.head{left:16px;right:10px}h2{font-size:clamp(17px,1.65vw,26px)}}
    @media(max-width:820px){.tour{width:2340px;height:300px}.stage{height:300px}}
    @media(prefers-reduced-motion:reduce){.draw{transition:none;stroke-dashoffset:0}}</style><div class="tour"><!-- Une seule silhouette extérieure continue pour les neuf étapes -->
    <svg class="connector" viewBox="0 0 5400 360" preserveAspectRatio="none" aria-hidden="true">
      <defs><filter id="roughMain" x="-2%" y="-5%" width="104%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".005 .045" numOctaves="2" seed="51" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.1"/></filter></defs>
      <path class="ghost" d="M0 299 C42 286 72 259 108 239 C144 219 167 189 201 186 C238 183 263 198 292 200 C326 202 345 179 374 175 C408 170 430 188 454 188 C478 188 491 158 519 152 C548 146 571 194 600 215 C640 227 682 245 722 226 C758 223 780 233 806 218 L832 195 L852 208 L875 184 L896 202 L921 206 L945 222 C968 209 986 189 1006 169 C1030 145 1048 117 1078 100 C1110 82 1154 149 1200 179 C1218 165 1233 168 1253 160 L1277 153 L1296 161 L1319 149 L1344 154 L1368 137 L1394 107 L1417 116 L1436 97 L1465 104 L1486 83 L1517 68 L1545 77 L1570 103 L1595 111 L1617 132 L1638 124 L1658 144 L1681 150 L1706 133 L1729 142 L1753 164 L1776 171 L1800 188 C1825 177 1845 158 1867 151 L1890 158 L1914 141 L1939 148 L1963 129 L1988 135 L2014 111 L2040 117 L2065 96 L2092 84 L2120 72 L2148 80 L2174 101 L2201 108 L2226 124 L2251 117 L2278 139 L2303 121 L2329 132 L2354 110 L2377 128 L2400 155 C2424 151 2449 143 2473 126 C2492 113 2514 109 2537 125 C2560 141 2580 137 2601 118 C2624 98 2648 105 2670 121 C2693 138 2714 126 2738 104 C2761 84 2785 82 2808 101 C2831 119 2852 112 2875 92 C2897 74 2921 82 2942 105 C2962 127 2981 142 3000 151"/>
      <path class="hover-line hover-1" pathLength="1" d="M0 299 C42 286 72 259 108 239 C144 219 167 189 201 186 C238 183 263 198 292 200 C326 202 345 179 374 175 C408 170 430 188 454 188 C478 188 491 158 519 152 C548 146 571 194 600 215"/>
      <path class="hover-line hover-2" pathLength="1" d="M600 215 C640 227 682 245 722 226 C758 223 780 233 806 218 L832 195 L852 208 L875 184 L896 202 L921 206 L945 222 C968 209 986 189 1006 169 C1030 145 1048 117 1078 100 C1110 82 1154 149 1200 179"/>
      <path class="hover-line hover-3" pathLength="1" d="M1200 179 C1218 165 1233 168 1253 160 L1277 153 L1296 161 L1319 149 L1344 154 L1368 137 L1394 107 L1417 116 L1436 97 L1465 104 L1486 83 L1517 68 L1545 77 L1570 103 L1595 111 L1617 132 L1638 124 L1658 144 L1681 150 L1706 133 L1729 142 L1753 164 L1776 171 L1800 188"/>
      <path class="hover-line hover-4" pathLength="1" d="M1800 188 C1825 177 1845 158 1867 151 L1890 158 L1914 141 L1939 148 L1963 129 L1988 135 L2014 111 L2040 117 L2065 96 L2092 84 L2120 72 L2148 80 L2174 101 L2201 108 L2226 124 L2251 117 L2278 139 L2303 121 L2329 132 L2354 110 L2377 128 L2400 155"/>
      <path class="hover-line hover-5" pathLength="1" d="M2400 155 C2424 151 2449 143 2473 126 C2492 113 2514 109 2537 125 C2560 141 2580 137 2601 118 C2624 98 2648 105 2670 121 C2693 138 2714 126 2738 104 C2761 84 2785 82 2808 101 C2831 119 2852 112 2875 92 C2897 74 2921 82 2942 105 C2962 127 2981 142 3000 151"/>
      <path class="ghost" d="M3000 151 C3040 147 3079 137 3117 121 C3160 103 3202 82 3244 78 C3288 73 3326 84 3365 104 C3404 124 3442 146 3484 164 C3524 181 3563 191 3600 198"/>
      <path class="hover-line hover-6" pathLength="1" d="M3000 151 C3040 147 3079 137 3117 121 C3160 103 3202 82 3244 78 C3288 73 3326 84 3365 104 C3404 124 3442 146 3484 164 C3524 181 3563 191 3600 198"/>
      <path class="ghost" d="M3600 198 C3634 184 3666 164 3695 142 L3720 148 L3747 126 L3772 133 L3798 108 L3826 86 L3853 62 L3882 52 L3910 59 L3937 78 L3961 102 L3985 126 L4010 141 L4035 164 L4062 155 L4088 177 L4115 171 L4141 191 L4168 184 L4200 201 C4230 191 4258 171 4286 150 C4314 129 4344 112 4375 103 C4406 94 4438 101 4468 119 C4497 136 4525 143 4554 132 C4584 121 4614 126 4642 145 C4670 164 4698 178 4728 183 C4757 188 4782 184 4800 176 C4827 165 4853 147 4879 124 L4903 132 L4928 111 L4953 118 L4978 96 L5005 75 L5032 56 L5060 68 L5087 91 L5114 82 L5141 105 L5168 99 L5196 123 L5223 116 L5250 141 L5278 135 L5306 158 L5334 151 L5364 176 L5400 188"/>
      <path class="hover-line hover-7" pathLength="1" d="M3600 198 C3634 184 3666 164 3695 142 L3720 148 L3747 126 L3772 133 L3798 108 L3826 86 L3853 62 L3882 52 L3910 59 L3937 78 L3961 102 L3985 126 L4010 141 L4035 164 L4062 155 L4088 177 L4115 171 L4141 191 L4168 184 L4200 201"/>
      <path class="hover-line hover-8" pathLength="1" d="M4200 201 C4230 191 4258 171 4286 150 C4314 129 4344 112 4375 103 C4406 94 4438 101 4468 119 C4497 136 4525 143 4554 132 C4584 121 4614 126 4642 145 C4670 164 4698 178 4728 183 C4757 188 4782 184 4800 176"/>
      <path class="hover-line hover-9" pathLength="1" d="M4800 176 C4827 165 4853 147 4879 124 L4903 132 L4928 111 L4953 118 L4978 96 L5005 75 L5032 56 L5060 68 L5087 91 L5114 82 L5141 105 L5168 99 L5196 123 L5223 116 L5250 141 L5278 135 L5306 158 L5334 151 L5364 176 L5400 188"/>
    </svg>
    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 01</div><h2>Mona Yongpyong</h2><div class="meta">🇰🇷 South Korea</div></header>
      <svg class="s1" viewBox="0 0 600 360" aria-label="Profil de Mona Yongpyong">
        <defs><filter id="rough1" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".012 .055" numOctaves="2" seed="11" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.2"/></filter></defs><g transform="translate(0 10)">
        <path class="shade" d="M201 176 C238 173 263 188 292 190 C267 229 242 264 215 310 L164 310 C183 263 207 215 201 176 Z"/>
        <path class="shade" d="M519 142 C547 136 568 210 600 310 L467 310 C488 265 516 205 519 142 Z"/>
        <path class="hatch" d="M184 221 L234 267 M176 242 L224 286 M491 211 L545 258 M480 237 L556 292"/>
        <path class="ghost detail accent" pathLength="1" d="M88 310 C107 274 123 231 137 199 C149 177 168 171 201 176 C213 207 205 246 186 281 C176 299 168 307 164 310"/>
        <path class="ghost detail" pathLength="1" d="M245 310 C263 276 283 239 301 211 C319 184 342 171 374 165 C385 196 376 226 357 252 C338 279 325 296 318 310"/>
        <path class="ghost detail accent" pathLength="1" d="M404 310 C430 273 455 235 474 199 C489 171 501 148 519 142 C532 170 525 203 510 231 C492 264 476 290 467 310"/>
        </g></svg>
      <button aria-label="Révéler l’étape 1"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 02</div><h2>Loudenvielle</h2><div class="meta">🇫🇷 France</div></header>
      <svg class="s2" viewBox="0 0 600 360" aria-label="Profil de Loudenvielle et de sa vallée">
        <defs><filter id="rough2" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".014 .05" numOctaves="2" seed="22" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.1"/></filter></defs><g transform="translate(0 25)">
        <path class="shade" d="M321 181 C368 184 386 164 406 144 C430 120 448 92 478 75 C486 143 464 217 421 264 C382 244 352 213 321 181 Z"/>
        <path class="shade" d="M0 310 C42 271 82 220 122 201 C159 213 185 248 164 269 C108 281 54 296 0 310 Z"/>
        <path class="hatch" d="M380 184 L429 226 M392 161 L445 207 M408 138 L458 185 M63 252 L106 283 M84 230 L132 267"/>
        <path class="ghost detail" pathLength="1" d="M0 239 C67 249 112 258 164 269 C221 281 268 272 321 181"/>
        <path class="ghost detail" pathLength="1" d="M321 181 C352 213 382 244 421 264 C469 288 521 291 600 279"/>
        <path class="ghost detail accent" pathLength="1" d="M36 310 C112 284 191 282 269 294 C345 306 427 308 559 286 C532 318 469 329 376 327 C258 325 145 316 36 310"/>
        <path class="ghost detail" pathLength="1" d="M390 310 C426 266 450 220 472 172 C492 127 502 92 478 75"/>
        </g></svg>
      <button aria-label="Révéler l’étape 2"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 03</div><h2>Leogang</h2><div class="meta">🇦🇹 Autriche</div></header>
      <svg class="s3" viewBox="0 0 600 360" aria-label="Profil rocheux de Leogang">
        <defs><filter id="rough3" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".016 .06" numOctaves="2" seed="33" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.4"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M53 155 L77 148 L96 156 L119 144 L144 149 L168 132 L194 102 C188 173 157 232 111 276 C77 291 40 302 0 310 C18 251 31 183 53 155 Z"/>
        <path class="shade" d="M317 63 L345 72 L370 98 L395 106 L417 127 C407 185 371 236 328 269 C295 282 259 294 221 300 C269 224 302 146 317 63 Z"/>
        <path class="hatch" d="M70 178 L139 231 M83 157 L153 211 M104 153 L170 197 M293 111 L373 175 M305 86 L385 150 M326 78 L402 136 M440 155 L505 208 M459 147 L523 193"/>
        <path class="ghost detail" pathLength="1" d="M0 269 C73 241 135 223 194 102 C215 153 245 187 288 215 C327 240 368 248 417 127"/>
        <path class="ghost detail" pathLength="1" d="M194 102 C231 154 268 188 317 63 C339 128 366 171 417 205 C457 231 510 250 600 267"/>
        <path class="ghost detail accent" pathLength="1" d="M160 310 C195 264 229 232 268 211 C305 191 334 158 345 72 C364 139 376 200 403 242 C421 270 446 291 474 310"/>
        </g></svg>
      <button aria-label="Révéler l’étape 3"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 04</div><h2>Lenzerheide</h2><div class="meta">🇨🇭 Suisse</div></header>
      <svg class="s4" viewBox="0 0 600 360" aria-label="Profil enneigé de Lenzerheide">
        <defs><filter id="rough4" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".013 .05" numOctaves="2" seed="44" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.2"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M40 270 C90 220 145 166 212 72 C210 145 183 216 135 270 C100 290 70 300 40 305 Z"/>
        <path class="shade" d="M354 110 L377 128 L400 155 C380 213 348 258 305 292 C324 230 342 171 354 110 Z"/>
        <path class="hatch" d="M83 219 L144 257 M105 190 L163 231 M128 160 L181 204 M180 111 L229 157 M199 91 L247 138 M330 165 L386 210 M348 137 L401 183"/>
        <path class="ghost detail" pathLength="1" d="M28 286 C92 249 144 190 212 72 C235 137 270 177 321 204 C357 224 397 226 432 188"/>
        <path class="ghost detail" pathLength="1" d="M212 72 C257 115 296 149 354 110 C384 164 421 202 472 229 C513 250 555 259 600 260"/>
        <path class="ghost detail accent" pathLength="1" d="M110 310 C145 268 179 228 211 181 C236 145 253 112 265 88 C286 149 306 205 341 245 C365 273 395 294 428 310"/>
        </g></svg>
      <button aria-label="Révéler l’étape 4"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 05</div><h2>Whistler</h2><div class="meta">🇨🇦 Canada</div></header>
      <svg class="s5" viewBox="0 0 600 360" aria-label="Profil enneigé de Whistler">
        <defs><filter id="rough5" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".017 .058" numOctaves="2" seed="55" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.5"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M73 121 C112 93 143 113 170 116 C146 181 116 234 72 272 C50 251 32 225 22 194 C39 161 56 137 73 121 Z"/>
        <path class="shade" d="M338 96 C369 72 394 78 418 97 C408 159 382 218 340 265 C310 250 284 228 263 200 C292 158 315 123 338 96 Z"/>
        <path class="hatch" d="M55 153 L112 198 M76 127 L133 173 M105 119 L153 157 M228 132 L282 173 M250 113 L301 153 M329 116 L390 165 M350 94 L409 141 M374 91 L425 130 M452 137 L505 180"/>
        <path class="ghost detail" pathLength="1" d="M0 274 C69 248 119 212 170 116 C205 154 237 174 276 188 C313 201 350 190 418 97"/>
        <path class="ghost detail" pathLength="1" d="M170 116 C219 113 254 118 301 153 C340 181 382 188 418 97 C451 146 489 181 538 207 C559 218 580 226 600 229"/>
        <path class="ghost detail" pathLength="1" d="M73 121 C112 166 146 199 192 221 C241 245 289 248 338 96"/>
        <path class="ghost detail accent" pathLength="1" d="M0 310 C76 289 139 278 201 286 C264 294 326 310 389 299 C457 288 526 260 600 236"/>
        </g></svg>
      <button aria-label="Révéler l’étape 5"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 06</div><h2>Lake Placid</h2><div class="meta">🇺🇸 United States</div></header>
      <svg class="s6" viewBox="0 0 600 360" aria-label="Profil arrondi de Lake Placid">
        <defs><filter id="rough6" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".012 .045" numOctaves="2" seed="66" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.3"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M0 270 C78 239 145 187 244 78 C233 151 207 216 166 269 C111 286 56 297 0 306 Z"/>
        <path class="shade" d="M244 78 C300 73 341 88 365 104 C348 177 316 232 269 276 C234 259 206 236 184 208 C211 156 230 112 244 78 Z"/>
        <path class="hatch" d="M74 218 L137 259 M96 193 L158 235 M121 166 L181 211 M151 138 L204 181 M184 108 L231 149 M271 103 L329 147 M294 107 L349 151 M321 119 L374 160 M386 138 L438 179"/>
        <path class="ghost detail" pathLength="1" d="M0 273 C83 249 153 194 244 78 C268 148 299 204 347 242 C392 277 449 291 520 292"/>
        <path class="ghost detail" pathLength="1" d="M75 310 C123 276 166 245 207 208 C249 170 287 131 325 95 C365 128 406 164 453 196 C501 229 551 248 600 258"/>
        <path class="ghost detail" pathLength="1" d="M244 78 C295 73 333 87 365 104 C401 123 439 147 478 172"/>
        <path class="ghost detail accent" pathLength="1" d="M0 310 C91 288 177 283 254 294 C332 305 402 307 469 292 C516 282 560 263 600 240"/>
        </g></svg>
      <button aria-label="Révéler l’étape 6"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 07</div><h2>La Thuile</h2><div class="meta">🇮🇹 Italie</div></header>
      <svg class="s7" viewBox="0 0 600 360" aria-label="Profil rocheux et enneigé de La Thuile">
        <defs><filter id="rough7" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".017 .058" numOctaves="2" seed="77" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.5"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M78 142 L120 132 L168 119 L220 83 L276 48 C269 126 246 196 208 258 C166 245 129 219 100 184 Z"/>
        <path class="shade" d="M276 48 L308 53 L335 65 L358 86 L381 108 L405 122 C388 186 358 242 315 283 C283 255 258 220 244 181 C263 132 274 88 276 48 Z"/>
        <path class="hatch" d="M116 150 L181 199 M139 131 L202 180 M166 113 L224 158 M200 85 L251 130 M243 61 L292 105 M292 76 L350 126 M334 120 L389 168 M405 158 L456 201"/>
        <path class="ghost detail" pathLength="1" d="M20 286 C78 254 117 208 168 119 C206 94 238 68 276 48 C268 119 245 180 208 228 C175 270 135 295 84 310"/>
        <path class="ghost detail" pathLength="1" d="M276 48 C301 110 326 168 365 215 C392 247 427 269 474 282 C518 294 558 294 600 288"/>
        <path class="ghost detail" pathLength="1" d="M168 119 C209 150 239 184 264 231 C291 279 330 302 388 310"/>
        <path class="ghost detail accent" pathLength="1" d="M0 310 C71 284 140 276 207 289 C278 303 340 316 402 305 C471 293 535 267 600 240"/>
        </g></svg>
      <button aria-label="Révéler l’étape 7"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 08</div><h2>Les Gets</h2><div class="meta">🇫🇷 France</div></header>
      <svg class="s8" viewBox="0 0 600 360" aria-label="Profil boisé des Gets">
        <defs><filter id="rough8" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".014 .05" numOctaves="2" seed="88" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.3"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M0 286 C72 253 130 192 175 103 C190 172 181 229 148 273 C101 292 52 302 0 310 Z"/>
        <path class="shade" d="M354 132 C389 113 423 119 442 145 C427 201 398 247 356 279 C326 263 301 240 280 211 C309 178 333 151 354 132 Z"/>
        <path class="hatch" d="M73 226 L127 260 M92 201 L148 239 M114 172 L165 211 M132 142 L177 180 M332 170 L388 211 M354 144 L407 185 M385 137 L431 173"/>
        <path class="ghost detail" pathLength="1" d="M0 279 C72 246 126 186 175 103 C204 165 239 204 285 230 C332 257 385 255 442 145"/>
        <path class="ghost detail" pathLength="1" d="M175 103 C224 119 265 145 302 181 C339 217 383 231 442 145 C480 196 529 226 600 241"/>
        <path class="ghost detail accent" pathLength="1" d="M0 310 C89 289 174 285 252 297 C328 309 398 304 461 283 C513 266 559 243 600 218"/>
        </g></svg>
      <button aria-label="Révéler l’étape 8"></button>
    </section>

    <section class="stage" tabindex="0">
      <header class="head"><div class="number">Event 09</div><h2>Pal Arinsal</h2><div class="meta">🇦🇩 Andorre</div></header>
      <svg class="s9" viewBox="0 0 600 360" aria-label="Profil pyrénéen de Pal Arinsal">
        <defs><filter id="rough9" x="-3%" y="-5%" width="106%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".018 .06" numOctaves="2" seed="99" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.6"/></filter></defs><g transform="translate(0 5)">
        <path class="shade" d="M79 119 L128 91 L175 51 C173 132 148 206 106 264 C72 282 37 296 0 306 C26 228 51 166 79 119 Z"/>
        <path class="shade" d="M175 51 L203 63 L230 86 L257 77 L284 100 C275 169 247 229 207 275 C174 249 149 219 132 183 C153 135 168 91 175 51 Z"/>
        <path class="hatch" d="M67 165 L128 210 M86 136 L147 183 M111 106 L164 151 M145 73 L194 118 M190 76 L249 123 M211 94 L268 139 M295 128 L351 171 M321 120 L374 160"/>
        <path class="ghost detail" pathLength="1" d="M0 276 C69 242 118 174 175 51 C199 116 228 167 273 211 C313 250 360 270 417 276"/>
        <path class="ghost detail" pathLength="1" d="M175 51 C218 95 249 130 284 100 C330 153 370 192 421 220 C471 248 531 257 600 247"/>
        <path class="ghost detail accent" pathLength="1" d="M0 310 C83 287 158 283 228 295 C302 308 373 306 441 287 C500 271 553 243 600 212"/>
        </g></svg>
      <button aria-label="Révéler l’étape 9"></button>
    </section></div>`;
    root.querySelectorAll('.stage').forEach(stage => {
      const svg = stage.querySelector('svg');
      svg.querySelectorAll('.ghost').forEach(path => {
        const active = path.cloneNode();
        active.classList.remove('ghost');
        active.classList.add('draw');
        path.parentNode.appendChild(active);
      });
      stage.querySelector('button').addEventListener('click', () => {
        if(matchMedia('(hover: none)').matches) stage.classList.toggle('active');
      });
    });
  }
}
if(!customElements.get('uci-iconic-tour')) customElements.define('uci-iconic-tour', UciIconicTour);
