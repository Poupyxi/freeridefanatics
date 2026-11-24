(()=>{const state={items:[],index:0,modal:null};function close(){state.modal?.remove();state.modal=null;document.body.classList.remove("setup-share-open")}function render(){const i=state.items[state.index];if(!i)return;state.modal.querySelector("[data-setup-share-image]").src=i.image;state.modal.querySelector("[data-setup-share-image]").alt=i.title;state.modal.querySelector("[data-setup-share-title]").textContent=i.title;state.modal.querySelector("[data-setup-share-category]").textContent=i.category;state.modal.querySelector("[data-setup-share-count]").textContent=`${state.index+1} / ${state.items.length}`}function open(){state.items=[...document.querySelectorAll(".bb-part")].map(c=>{const b=c.querySelector(".bb-photo");if(!b)return null;return{image:b.getAttribute("src"),title:c.querySelector(".bb-name")?.textContent.trim()||b.alt||"Equipment",category:c.querySelector(".bb-cat")?.textContent.trim()||"Equipment"}}).concat([...document.querySelectorAll("[data-equipment-card]")].map(c=>{const b=c.querySelector("[data-equipment-image]");if(!b)return null;return{image:b.dataset.equipmentImage,title:b.dataset.equipmentTitle||c.querySelector("h4")?.textContent.trim()||"Equipment",category:c.querySelector(".cat")?.textContent.trim()||"Equipment"}})).filter(Boolean);const order={"Frame":0,"Fork":1,"Rear shock":2,"Shox":2,"Handlebar":3,"Brake":4,"Wheels":5,"Tyres":6,"Crankset":7,"Derailleur":8,"Stems":9,"Seatpost":10,"Saddle":11};state.items.sort((a,b)=>(order[a.category]??50)-(order[b.category]??50)||a.title.localeCompare(b.title));if(!state.items.length)return;state.index=0;const m=document.createElement("div");m.className="setup-share-modal";m.innerHTML=`<div class="setup-share-backdrop" data-setup-close></div><section class="setup-share-dialog" role="dialog" aria-modal="true" aria-label="Share rider setup"><button class="setup-share-close" type="button" data-setup-close aria-label="Close">×</button><div class="setup-share-kicker">RIDER SETUP</div><h2>${document.querySelector("h1")?.textContent.trim()||document.title}</h2><div class="setup-share-preview"><button type="button" class="setup-share-arrow" data-setup-prev aria-label="Previous">‹</button><img data-setup-share-image alt=""><button type="button" class="setup-share-arrow" data-setup-next aria-label="Next">›</button></div><div class="setup-share-meta"><span data-setup-share-category></span><strong data-setup-share-title></strong><small data-setup-share-count></small></div><div class="setup-share-caption" data-setup-caption></div><div class="setup-share-actions"><button type="button" data-setup-download-card>Download this image</button><button type="button" data-setup-copy-post>Copy post</button><button type="button" data-setup-copy>Copy link</button><button type="button" data-setup-native-share>Share</button></div><div class="setup-share-socials" aria-label="Share on social networks"><a data-social="instagram" href="https://www.instagram.com/" target="_blank" rel="noopener">Instagram</a><a data-social="x" href="#" target="_blank" rel="noopener">X</a><a data-social="facebook" href="#" target="_blank" rel="noopener">Facebook</a><a data-social="linkedin" href="#" target="_blank" rel="noopener">LinkedIn</a></div></section>`;document.body.append(m);state.modal=m;const rider=(document.querySelector("h1")?.textContent.trim()||document.title).replace(/\s+/g," ");const riderHandle="@"+rider.toLowerCase().replace(/[^a-z0-9]+/g,"");const equipmentText=state.items.map(i=>{const parts=i.title.split(/\s+/);const brand=parts.shift()||"brand";return `@${brand.toLowerCase().replace(/[^a-z0-9]+/g,"")}: ${parts.join(" ")}`}).join("\n");const competitions=[...document.querySelectorAll("[data-results-table] tbody tr td:nth-child(2)")].map(x=>x.textContent.trim()).filter(Boolean).filter((x,i,a)=>a.indexOf(x)===i);const compText=competitions.length?`He participated in ${competitions.slice(0,6).join(", ")}.`:"Competition appearances recorded in the RidersFanatics database.";const caption=`Here is the equipment of ${riderHandle} during the 2026 season.\n\n${equipmentText}\n\n${compText}\n\n#BikeCheck #Downhill #MountainBike`;m.querySelector("[data-setup-caption]").textContent=caption;const u=encodeURIComponent(location.href),t=encodeURIComponent(document.title);m.querySelector("[data-social=\"x\"]").href=`https://twitter.com/intent/tweet?url=${u}&text=${t}`;m.querySelector("[data-social=\"facebook\"]").href=`https://www.facebook.com/sharer/sharer.php?u=${u}`;m.querySelector("[data-social=\"linkedin\"]").href=`https://www.linkedin.com/sharing/share-offsite/?url=${u}`;document.body.classList.add("setup-share-open");render();previewCard().then(data=>{if(data&&state.modal===m){state.items.unshift({image:data,title:"Bike setup flat lay",category:"Bike check"});state.index=0;render()}})}async function previewCard(){
  const parts=state.items.filter(item=>item && item.image && item.category!=="Bike check");
  if(!parts.length)return null;
  const canvas=document.createElement("canvas"),ctx=canvas.getContext("2d");
  if(!ctx)return null;
  canvas.width=1080;canvas.height=1350;
  const loadImage=src=>new Promise(resolve=>{
    const image=new Image();
    image.crossOrigin="anonymous";
    image.onload=()=>resolve(image);
    image.onerror=()=>resolve(null);
    image.src=src;
  });
  const wood=await loadImage("/assets/img/share/bikecheck-wood.png");
  if(!wood)return null;
  const cover=Math.max(canvas.width/wood.width,canvas.height/wood.height);
  const sourceWidth=canvas.width/cover,sourceHeight=canvas.height/cover;
  ctx.drawImage(wood,(wood.width-sourceWidth)/2,(wood.height-sourceHeight)/2,sourceWidth,sourceHeight,0,0,canvas.width,canvas.height);
  const rider=(document.querySelector("h1")?.textContent.trim()||"Rider").toUpperCase();
  ctx.fillStyle="rgba(20,9,4,.30)";ctx.fillRect(0,0,1080,158);
  ctx.textAlign="center";ctx.textBaseline="middle";
  let size=78;
  do{ctx.font="900 "+size+"px Arial, sans-serif";if(ctx.measureText(rider).width<=1010)break;size-=2}while(size>34);
  ctx.fillStyle="#150905";ctx.shadowColor="#0b0402";ctx.shadowBlur=5;ctx.fillText(rider,540,67);
  ctx.shadowBlur=0;ctx.fillStyle="rgba(255,166,87,.52)";ctx.fillText(rider,539,65);
  ctx.fillStyle="#1a0b05";ctx.fillText(rider,540,68);
  ctx.fillStyle="#ad481d";ctx.fillRect(0,120,1080,45);
  ctx.fillStyle="#fff7ea";ctx.font="700 27px Arial, sans-serif";ctx.fillText("BIKE CHECK",540,143);
  ctx.textAlign="right";ctx.font="700 28px Arial, sans-serif";
  ctx.shadowColor="rgba(0,0,0,.9)";ctx.shadowBlur=8;
  ctx.fillStyle="#ffffff";ctx.fillText("RIDERSFANATICS",1036,1307);
  ctx.shadowBlur=0;
  function transparentProduct(image){
    const maxSide=850,scale=Math.min(1,maxSide/Math.max(image.width,image.height));
    const work=document.createElement("canvas");
    work.width=Math.max(1,Math.round(image.width*scale));
    work.height=Math.max(1,Math.round(image.height*scale));
    const wctx=work.getContext("2d",{willReadFrequently:true});
    wctx.drawImage(image,0,0,work.width,work.height);
    let data;
    try{data=wctx.getImageData(0,0,work.width,work.height)}catch{return null}
    const pixels=data.data,width=work.width,height=work.height;
    // Estimate the studio backdrop independently on each row: many Drive photos
    // have a grey gradient, not a uniformly white background.
    const edge=Math.max(1,Math.min(5,Math.floor(width/12)));
    const backdrop=new Float32Array(height*6);
    for(let y=0;y<height;y++)for(let side=0;side<2;side++){
      const offset=y*6+side*3;
      for(let k=0;k<edge;k++){
        const x=side?width-1-k:k,p=(y*width+x)*4;
        for(let c=0;c<3;c++)backdrop[offset+c]+=pixels[p+c]/edge;
      }
    }
    const distance=(x,y)=>{
      const p=(y*width+x)*4,t=width>1?x/(width-1):0,q=y*6;
      let sum=0;
      for(let c=0;c<3;c++){const delta=pixels[p+c]-(backdrop[q+c]*(1-t)+backdrop[q+3+c]*t);sum+=delta*delta}
      return Math.sqrt(sum);
    };
    const seen=new Uint8Array(width*height),queue=new Int32Array(width*height);
    let head=0,tail=0;
    const add=(x,y)=>{
      const i=y*width+x,p=i*4;
      if(seen[i]||pixels[p+3]<8||distance(x,y)>43)return;
      seen[i]=1;queue[tail++]=i;
    };
    for(let x=0;x<width;x++){add(x,0);add(x,height-1)}
    for(let y=0;y<height;y++){add(0,y);add(width-1,y)}
    while(head<tail){
      const i=queue[head++],x=i%width,y=(i-x)/width;
      if(x>0)add(x-1,y);if(x<width-1)add(x+1,y);
      if(y>0)add(x,y-1);if(y<height-1)add(x,y+1);
    }
    const removed=tail/(width*height);
    // Complex photos must stay in the following individual slides, never as a
    // visible rectangular patch on the wooden cover.
    let transparent=0;
    for(let i=3;i<pixels.length;i+=4)if(pixels[i]<8)transparent++;
    if(removed<.25&&transparent/(width*height)<.12)return null;
    for(let i=0;i<width*height;i++)if(seen[i])pixels[i*4+3]=0;
    // Suppress isolated photographic shadows/noise, preserving separate parts.
    const visited=new Uint8Array(width*height),components=[];
    for(let i=0;i<width*height;i++){
      if(visited[i]||pixels[i*4+3]<25)continue;
      let start=0,end=0;queue[end++]=i;visited[i]=1;
      while(start<end){
        const n=queue[start++],x=n%width,y=(n-x)/width;
        const neighbors=[x>0?n-1:-1,x<width-1?n+1:-1,y>0?n-width:-1,y<height-1?n+width:-1];
        for(const m of neighbors)if(m>=0&&!visited[m]&&pixels[m*4+3]>=25){visited[m]=1;queue[end++]=m}
      }
      components.push({size:end,indices:queue.slice(0,end)});
    }
    let largest=0;
    for(const component of components)largest=Math.max(largest,component.size);
    const minimum=Math.max(30,largest*.025);
    for(const component of components)if(component.size<minimum)for(const i of component.indices)pixels[i*4+3]=0;
    // Avoid a hard JPEG fringe along the cutout boundary.
    for(let y=1;y<height-1;y++)for(let x=1;x<width-1;x++){
      const i=y*width+x,p=i*4;
      if(pixels[p+3]<25)continue;
      if(!pixels[p-1]||!pixels[p+7]||!pixels[p-width*4+3]||!pixels[p+width*4+3])pixels[p+3]=Math.min(pixels[p+3],Math.max(80,Math.round((65-distance(x,y))*4)));
    }
    wctx.putImageData(data,0,0);
    let left=width,top=height,right=-1,bottom=-1;
    for(let y=0;y<height;y++)for(let x=0;x<width;x++){
      const p=(y*width+x)*4;if(pixels[p+3]<25)continue;
      if(x<left)left=x;if(x>right)right=x;if(y<top)top=y;if(y>bottom)bottom=y;
    }
    return right>=0?{canvas:work,bounds:{x:left,y:top,w:right-left+1,h:bottom-top+1}}:null;
  }
  async function place(item,box){
    if(!item)return;
    const image=await loadImage(item.image);if(!image)return;
    const prepared=transparentProduct(image);if(!prepared)return;
    const b=prepared.bounds;
    const scale=Math.min(box.w/b.w,box.h/b.h),w=b.w*scale,h=b.h*scale;
    const x=box.x+(box.w-w)/2,y=box.y+(box.h-h)/2;
    ctx.save();ctx.shadowColor="rgba(5,3,2,.72)";ctx.shadowBlur=22;
    ctx.shadowOffsetX=9;ctx.shadowOffsetY=13;
    ctx.drawImage(prepared.canvas,b.x,b.y,b.w,b.h,x,y,w,h);
    ctx.restore();
  }
  const category=item=>(item.category||"").toLowerCase();
  const find=pattern=>parts.find(item=>pattern.test(category(item)));
  const frame=find(/frame/),fork=find(/fork/),shock=find(/rear shock|shox/);
  const wheels=parts.filter(item=>/wheel/.test(category(item)));
  const handlebar=find(/handlebar/);
  const used=new Set([frame,fork,shock,handlebar,...wheels]);
  const small=parts.filter(item=>!used.has(item)).slice(0,7);
  await place(handlebar,{x:280,y:188,w:520,h:95});
  if(wheels[0])await place(wheels[0],{x:35,y:320,w:265,h:315});
  if(wheels[1])await place(wheels[1],{x:35,y:645,w:265,h:315});
  await place(frame,{x:255,y:320,w:625,h:590});
  await place(fork,{x:860,y:260,w:190,h:690});
  await place(shock,{x:560,y:900,w:285,h:135});
  for(let i=0;i<small.length;i++){
    const col=i%4,row=Math.floor(i/4);
    await place(small[i],{x:80+col*245,y:1040+row*110,w:200,h:90});
  }
  try{return canvas.toDataURL("image/png")}catch{return null}
}async function downloadCard(){const current=state.items[state.index];if(!current?.image)return;const name=(document.querySelector("h1")?.textContent.trim()||"rider").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");const a=document.createElement("a");a.download=name+(state.index===0?"-bike-check.png":"-equipment-"+state.index+".png");a.href=current.image;a.click()}document.addEventListener("click",e=>{if(e.target.closest("[data-rider-setup-share]")){e.preventDefault();open()}if(e.target.closest("[data-setup-close]"))close();if(e.target.closest("[data-setup-prev]")){state.index=(state.index-1+state.items.length)%state.items.length;render()}if(e.target.closest("[data-setup-next]")){state.index=(state.index+1)%state.items.length;render()}if(e.target.closest("[data-setup-copy]")){navigator.clipboard?.writeText(location.href);e.target.textContent="Copied";setTimeout(()=>e.target.textContent="Copy link",1400)}if(e.target.closest("[data-setup-download-card]")){downloadCard()}if(e.target.closest("[data-setup-copy-post]")){navigator.clipboard?.writeText(state.modal.querySelector("[data-setup-caption]").textContent);e.target.textContent="Copied";setTimeout(()=>e.target.textContent="Copy post",1400)}if(e.target.closest("[data-setup-native-share]")&&navigator.share)navigator.share({title:document.title,url:location.href}).catch(()=>{})});document.addEventListener("keydown",e=>{if(!state.modal)return;if(e.key==="Escape")close();if(e.key==="ArrowRight"){state.index=(state.index+1)%state.items.length;render()}if(e.key==="ArrowLeft"){state.index=(state.index-1+state.items.length)%state.items.length;render()}})})();
