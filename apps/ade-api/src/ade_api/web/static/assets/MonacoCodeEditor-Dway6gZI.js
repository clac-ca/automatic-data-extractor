import{r as i,W as A,j as Q,c as Ce}from"./index-DDmClXr_.js";function fe(e,t){(t==null||t>e.length)&&(t=e.length);for(var r=0,n=Array(t);r<t;r++)n[r]=e[r];return n}function Re(e){if(Array.isArray(e))return e}function Pe(e,t,r){return(t=We(t))in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function Ae(e,t){var r=e==null?null:typeof Symbol<"u"&&e[Symbol.iterator]||e["@@iterator"];if(r!=null){var n,o,a,s,u=[],d=!0,f=!1;try{if(a=(r=r.call(e)).next,t!==0)for(;!(d=(n=a.call(r)).done)&&(u.push(n.value),u.length!==t);d=!0);}catch(v){f=!0,o=v}finally{try{if(!d&&r.return!=null&&(s=r.return(),Object(s)!==s))return}finally{if(f)throw o}}return u}}function Ie(){throw new TypeError(`Invalid attempt to destructure non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function me(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function ge(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?me(Object(r),!0).forEach(function(n){Pe(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):me(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function Te(e,t){if(e==null)return{};var r,n,o=De(e,t);if(Object.getOwnPropertySymbols){var a=Object.getOwnPropertySymbols(e);for(n=0;n<a.length;n++)r=a[n],t.indexOf(r)===-1&&{}.propertyIsEnumerable.call(e,r)&&(o[r]=e[r])}return o}function De(e,t){if(e==null)return{};var r={};for(var n in e)if({}.hasOwnProperty.call(e,n)){if(t.indexOf(n)!==-1)continue;r[n]=e[n]}return r}function $e(e,t){return Re(e)||Ae(e,t)||ze(e,t)||Ie()}function Le(e,t){if(typeof e!="object"||!e)return e;var r=e[Symbol.toPrimitive];if(r!==void 0){var n=r.call(e,t);if(typeof n!="object")return n;throw new TypeError("@@toPrimitive must return a primitive value.")}return(t==="string"?String:Number)(e)}function We(e){var t=Le(e,"string");return typeof t=="symbol"?t:t+""}function ze(e,t){if(e){if(typeof e=="string")return fe(e,t);var r={}.toString.call(e).slice(8,-1);return r==="Object"&&e.constructor&&(r=e.constructor.name),r==="Map"||r==="Set"?Array.from(e):r==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(r)?fe(e,t):void 0}}function He(e,t,r){return t in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function pe(e,t){var r=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter(function(o){return Object.getOwnPropertyDescriptor(e,o).enumerable})),r.push.apply(r,n)}return r}function he(e){for(var t=1;t<arguments.length;t++){var r=arguments[t]!=null?arguments[t]:{};t%2?pe(Object(r),!0).forEach(function(n){He(e,n,r[n])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(r)):pe(Object(r)).forEach(function(n){Object.defineProperty(e,n,Object.getOwnPropertyDescriptor(r,n))})}return e}function Ve(){for(var e=arguments.length,t=new Array(e),r=0;r<e;r++)t[r]=arguments[r];return function(n){return t.reduceRight(function(o,a){return a(o)},n)}}function L(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),a=0;a<n;a++)o[a]=arguments[a];return o.length>=e.length?e.apply(this,o):function(){for(var s=arguments.length,u=new Array(s),d=0;d<s;d++)u[d]=arguments[d];return t.apply(r,[].concat(o,u))}}}function q(e){return{}.toString.call(e).includes("Object")}function Be(e){return!Object.keys(e).length}function z(e){return typeof e=="function"}function Ke(e,t){return Object.prototype.hasOwnProperty.call(e,t)}function Fe(e,t){return q(t)||E("changeType"),Object.keys(t).some(function(r){return!Ke(e,r)})&&E("changeField"),t}function qe(e){z(e)||E("selectorType")}function Ue(e){z(e)||q(e)||E("handlerType"),q(e)&&Object.values(e).some(function(t){return!z(t)})&&E("handlersType")}function Ze(e){e||E("initialIsRequired"),q(e)||E("initialType"),Be(e)&&E("initialContent")}function Ge(e,t){throw new Error(e[t]||e.default)}var Ye={initialIsRequired:"initial state is required",initialType:"initial state should be an object",initialContent:"initial state shouldn't be an empty object",handlerType:"handler should be an object or a function",handlersType:"all handlers should be a functions",selectorType:"selector should be a function",changeType:"provided value of changes should be an object",changeField:'it seams you want to change a field in the state which is not specified in the "initial" state',default:"an unknown error accured in `state-local` package"},E=L(Ge)(Ye),K={changes:Fe,selector:qe,handler:Ue,initial:Ze};function Je(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{};K.initial(e),K.handler(t);var r={current:e},n=L(et)(r,t),o=L(Xe)(r),a=L(K.changes)(e),s=L(Qe)(r);function u(){var f=arguments.length>0&&arguments[0]!==void 0?arguments[0]:function(v){return v};return K.selector(f),f(r.current)}function d(f){Ve(n,o,a,s)(f)}return[u,d]}function Qe(e,t){return z(t)?t(e.current):t}function Xe(e,t){return e.current=he(he({},e.current),t),t}function et(e,t,r){return z(t)?t(e.current):Object.keys(r).forEach(function(n){var o;return(o=t[n])===null||o===void 0?void 0:o.call(t,e.current[n])}),r}var tt={create:Je},rt={paths:{vs:"https://cdn.jsdelivr.net/npm/monaco-editor@0.54.0/min/vs"}};function nt(e){return function t(){for(var r=this,n=arguments.length,o=new Array(n),a=0;a<n;a++)o[a]=arguments[a];return o.length>=e.length?e.apply(this,o):function(){for(var s=arguments.length,u=new Array(s),d=0;d<s;d++)u[d]=arguments[d];return t.apply(r,[].concat(o,u))}}}function ot(e){return{}.toString.call(e).includes("Object")}function at(e){return e||_e("configIsRequired"),ot(e)||_e("configType"),e.urls?(it(),{paths:{vs:e.urls.monacoBase}}):e}function it(){console.warn(be.deprecation)}function st(e,t){throw new Error(e[t]||e.default)}var be={configIsRequired:"the configuration object is required",configType:"the configuration object should be an object",default:"an unknown error accured in `@monaco-editor/loader` package",deprecation:`Deprecation warning!
    You are using deprecated way of configuration.

    Instead of using
      monaco.config({ urls: { monacoBase: '...' } })
    use
      monaco.config({ paths: { vs: '...' } })

    For more please check the link https://github.com/suren-atoyan/monaco-loader#config
  `},_e=nt(st)(be),ut={config:at},lt=function(){for(var t=arguments.length,r=new Array(t),n=0;n<t;n++)r[n]=arguments[n];return function(o){return r.reduceRight(function(a,s){return s(a)},o)}};function we(e,t){return Object.keys(t).forEach(function(r){t[r]instanceof Object&&e[r]&&Object.assign(t[r],we(e[r],t[r]))}),ge(ge({},e),t)}var ct={type:"cancelation",msg:"operation is manually canceled"};function X(e){var t=!1,r=new Promise(function(n,o){e.then(function(a){return t?o(ct):n(a)}),e.catch(o)});return r.cancel=function(){return t=!0},r}var dt=["monaco"],ft=tt.create({config:rt,isInitialized:!1,resolve:null,reject:null,monaco:null}),ke=$e(ft,2),H=ke[0],Z=ke[1];function mt(e){var t=ut.config(e),r=t.monaco,n=Te(t,dt);Z(function(o){return{config:we(o.config,n),monaco:r}})}function gt(){var e=H(function(t){var r=t.monaco,n=t.isInitialized,o=t.resolve;return{monaco:r,isInitialized:n,resolve:o}});if(!e.isInitialized){if(Z({isInitialized:!0}),e.monaco)return e.resolve(e.monaco),X(ee);if(window.monaco&&window.monaco.editor)return ye(window.monaco),e.resolve(window.monaco),X(ee);lt(pt,_t)(vt)}return X(ee)}function pt(e){return document.body.appendChild(e)}function ht(e){var t=document.createElement("script");return e&&(t.src=e),t}function _t(e){var t=H(function(n){var o=n.config,a=n.reject;return{config:o,reject:a}}),r=ht("".concat(t.config.paths.vs,"/loader.js"));return r.onload=function(){return e()},r.onerror=t.reject,r}function vt(){var e=H(function(r){var n=r.config,o=r.resolve,a=r.reject;return{config:n,resolve:o,reject:a}}),t=window.require;t.config(e.config),t(["vs/editor/editor.main"],function(r){var n=r.m;ye(n),e.resolve(n)},function(r){e.reject(r)})}function ye(e){H().monaco||Z({monaco:e})}function bt(){return H(function(e){var t=e.monaco;return t})}var ee=new Promise(function(e,t){return Z({resolve:e,reject:t})}),Ne={config:mt,init:gt,__getMonacoInstance:bt},wt={wrapper:{display:"flex",position:"relative",textAlign:"initial"},fullWidth:{width:"100%"},hide:{display:"none"}},te=wt,kt={container:{display:"flex",height:"100%",width:"100%",justifyContent:"center",alignItems:"center"}},yt=kt;function Nt({children:e}){return A.createElement("div",{style:yt.container},e)}var jt=Nt,Mt=jt;function St({width:e,height:t,isEditorReady:r,loading:n,_ref:o,className:a,wrapperProps:s}){return A.createElement("section",{style:{...te.wrapper,width:e,height:t},...s},!r&&A.createElement(Mt,null,n),A.createElement("div",{ref:o,style:{...te.fullWidth,...!r&&te.hide},className:a}))}var Ot=St,je=i.memo(Ot);function Et(e){i.useEffect(e,[])}var Me=Et;function xt(e,t,r=!0){let n=i.useRef(!0);i.useEffect(n.current||!r?()=>{n.current=!1}:e,t)}var N=xt;function W(){}function P(e,t,r,n){return Ct(e,n)||Rt(e,t,r,n)}function Ct(e,t){return e.editor.getModel(Se(e,t))}function Rt(e,t,r,n){return e.editor.createModel(t,r,n?Se(e,n):void 0)}function Se(e,t){return e.Uri.parse(t)}function Pt({original:e,modified:t,language:r,originalLanguage:n,modifiedLanguage:o,originalModelPath:a,modifiedModelPath:s,keepCurrentOriginalModel:u=!1,keepCurrentModifiedModel:d=!1,theme:f="light",loading:v="Loading...",options:_={},height:j="100%",width:C="100%",className:M,wrapperProps:S={},beforeMount:I=W,onMount:T=W}){let[b,x]=i.useState(!1),[h,l]=i.useState(!0),g=i.useRef(null),p=i.useRef(null),D=i.useRef(null),k=i.useRef(T),c=i.useRef(I),R=i.useRef(!1);Me(()=>{let m=Ne.init();return m.then(w=>(p.current=w)&&l(!1)).catch(w=>w?.type!=="cancelation"&&console.error("Monaco initialization: error:",w)),()=>g.current?$():m.cancel()}),N(()=>{if(g.current&&p.current){let m=g.current.getOriginalEditor(),w=P(p.current,e||"",n||r||"text",a||"");w!==m.getModel()&&m.setModel(w)}},[a],b),N(()=>{if(g.current&&p.current){let m=g.current.getModifiedEditor(),w=P(p.current,t||"",o||r||"text",s||"");w!==m.getModel()&&m.setModel(w)}},[s],b),N(()=>{let m=g.current.getModifiedEditor();m.getOption(p.current.editor.EditorOption.readOnly)?m.setValue(t||""):t!==m.getValue()&&(m.executeEdits("",[{range:m.getModel().getFullModelRange(),text:t||"",forceMoveMarkers:!0}]),m.pushUndoStop())},[t],b),N(()=>{g.current?.getModel()?.original.setValue(e||"")},[e],b),N(()=>{let{original:m,modified:w}=g.current.getModel();p.current.editor.setModelLanguage(m,n||r||"text"),p.current.editor.setModelLanguage(w,o||r||"text")},[r,n,o],b),N(()=>{p.current?.editor.setTheme(f)},[f],b),N(()=>{g.current?.updateOptions(_)},[_],b);let V=i.useCallback(()=>{if(!p.current)return;c.current(p.current);let m=P(p.current,e||"",n||r||"text",a||""),w=P(p.current,t||"",o||r||"text",s||"");g.current?.setModel({original:m,modified:w})},[r,t,o,e,n,a,s]),B=i.useCallback(()=>{!R.current&&D.current&&(g.current=p.current.editor.createDiffEditor(D.current,{automaticLayout:!0,..._}),V(),p.current?.editor.setTheme(f),x(!0),R.current=!0)},[_,f,V]);i.useEffect(()=>{b&&k.current(g.current,p.current)},[b]),i.useEffect(()=>{!h&&!b&&B()},[h,b,B]);function $(){let m=g.current?.getModel();u||m?.original?.dispose(),d||m?.modified?.dispose(),g.current?.dispose()}return A.createElement(je,{width:C,height:j,isEditorReady:b,loading:v,_ref:D,className:M,wrapperProps:S})}var At=Pt;i.memo(At);function It(e){let t=i.useRef();return i.useEffect(()=>{t.current=e},[e]),t.current}var Tt=It,F=new Map;function Dt({defaultValue:e,defaultLanguage:t,defaultPath:r,value:n,language:o,path:a,theme:s="light",line:u,loading:d="Loading...",options:f={},overrideServices:v={},saveViewState:_=!0,keepCurrentModel:j=!1,width:C="100%",height:M="100%",className:S,wrapperProps:I={},beforeMount:T=W,onMount:b=W,onChange:x,onValidate:h=W}){let[l,g]=i.useState(!1),[p,D]=i.useState(!0),k=i.useRef(null),c=i.useRef(null),R=i.useRef(null),V=i.useRef(b),B=i.useRef(T),$=i.useRef(),m=i.useRef(n),w=Tt(a),ce=i.useRef(!1),G=i.useRef(!1);Me(()=>{let y=Ne.init();return y.then(O=>(k.current=O)&&D(!1)).catch(O=>O?.type!=="cancelation"&&console.error("Monaco initialization: error:",O)),()=>c.current?xe():y.cancel()}),N(()=>{let y=P(k.current,e||n||"",t||o||"",a||r||"");y!==c.current?.getModel()&&(_&&F.set(w,c.current?.saveViewState()),c.current?.setModel(y),_&&c.current?.restoreViewState(F.get(a)))},[a],l),N(()=>{c.current?.updateOptions(f)},[f],l),N(()=>{!c.current||n===void 0||(c.current.getOption(k.current.editor.EditorOption.readOnly)?c.current.setValue(n):n!==c.current.getValue()&&(G.current=!0,c.current.executeEdits("",[{range:c.current.getModel().getFullModelRange(),text:n,forceMoveMarkers:!0}]),c.current.pushUndoStop(),G.current=!1))},[n],l),N(()=>{let y=c.current?.getModel();y&&o&&k.current?.editor.setModelLanguage(y,o)},[o],l),N(()=>{u!==void 0&&c.current?.revealLine(u)},[u],l),N(()=>{k.current?.editor.setTheme(s)},[s],l);let de=i.useCallback(()=>{if(!(!R.current||!k.current)&&!ce.current){B.current(k.current);let y=a||r,O=P(k.current,n||e||"",t||o||"",y||"");c.current=k.current?.editor.create(R.current,{model:O,automaticLayout:!0,...f},v),_&&c.current.restoreViewState(F.get(y)),k.current.editor.setTheme(s),u!==void 0&&c.current.revealLine(u),g(!0),ce.current=!0}},[e,t,r,n,o,a,f,v,_,s,u]);i.useEffect(()=>{l&&V.current(c.current,k.current)},[l]),i.useEffect(()=>{!p&&!l&&de()},[p,l,de]),m.current=n,i.useEffect(()=>{l&&x&&($.current?.dispose(),$.current=c.current?.onDidChangeModelContent(y=>{G.current||x(c.current.getValue(),y)}))},[l,x]),i.useEffect(()=>{if(l){let y=k.current.editor.onDidChangeMarkers(O=>{let Y=c.current.getModel()?.uri;if(Y&&O.find(J=>J.path===Y.path)){let J=k.current.editor.getModelMarkers({resource:Y});h?.(J)}});return()=>{y?.dispose()}}return()=>{}},[l,h]);function xe(){$.current?.dispose(),j?_&&F.set(a,c.current.saveViewState()):c.current.getModel()?.dispose(),c.current.dispose()}return A.createElement(je,{width:C,height:M,isEditorReady:l,loading:d,_ref:R,className:S,wrapperProps:I})}var $t=Dt,Lt=i.memo($t),Wt=Lt;function zt(e){return new Worker("/assets/editor.worker-B4pQIWZD.js",{name:e?.name})}function Ht(e){return new Worker("/assets/css.worker-DbrSMjj7.js",{name:e?.name})}function Vt(e){return new Worker("/assets/html.worker-Dy32WPZk.js",{name:e?.name})}function Bt(e){return new Worker("/assets/json.worker-jwAog0-I.js",{name:e?.name})}function Kt(e){return new Worker("/assets/ts.worker-B30KKKSO.js",{name:e?.name})}const Ft={kind:"row_detector",name:"detect_*",label:"ADE: row detector (detect_*)",signature:["def detect_*(","    *,","    row_index: int,","    row_values: list,","    sheet_name: str | None,","    metadata: dict | None,","    state: dict,","    input_file_name: str | None,","    logger,","    **_,",") -> dict[str, float] | None:"].join(`
`),doc:"Row detector entrypoint: vote for row kinds (e.g., header vs data). Return a mapping of RowKind→score deltas or None.",snippet:`
def detect_\${2:name}(
    *,
    row_index: int,
    row_values: list,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${3:Explain what this detector scores.}"""
    values = row_values or []
    non_empty = [v for v in values if v not in (None, "") and not (isinstance(v, str) and not v.strip())]
    density = len(non_empty) / max(len(values), 1) if values else 0.0
    score = min(1.0, density)
    return {"data": score, "header": -score * 0.2}
`.trim(),parameters:["row_index","row_values","sheet_name","metadata","state","input_file_name","logger"]},Oe={kind:"column_detector",name:"detect_*",label:"ADE: column detector (detect_*)",signature:["def detect_*(","    *,","    column_index: int,","    header,","    values,","    values_sample,","    sheet_name: str | None,","    metadata: dict | None,","    state: dict,","    input_file_name: str | None,","    logger,","    **_,",") -> dict[str, float] | None:"].join(`
`),doc:"Column detector entrypoint: score how likely the current raw column maps to a canonical field.",snippet:`
def detect_\${1:value_shape}(
    *,
    column_index: int,
    header,
    values,
    values_sample,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${2:Describe your heuristic for this field.}"""
    target_field = "\${3:field_name}"
    header_text = "" if header is None else str(header).strip().lower()
    if not header_text:
        return None
    if target_field.replace("_", " ") in header_text:
        return {target_field: 1.0}
    return None
`.trim(),parameters:["column_index","header","values","values_sample","sheet_name","metadata","state","input_file_name","logger"]},re={kind:"column_transform",name:"transform",label:"ADE: column transform",signature:["def transform(","    *,","    field_name: str,","    values,","    mapping,","    state: dict,","    metadata: dict | None,","    input_file_name: str | None,","    logger,","    **_,",") -> list[dict]:"].join(`
`),doc:"Column transform: normalize column values and emit row-indexed results. Return a list of {row_index, value}.",snippet:`
def transform(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Normalize or expand the values for this column.}"""
    results: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        normalized = text.title() if text else None
        results.append({"row_index": idx, "value": {field_name: normalized}})
    return results
`.trim(),parameters:["field_name","values","mapping","state","metadata","input_file_name","logger"]},ne={kind:"column_validator",name:"validate",label:"ADE: column validator",signature:["def validate(","    *,","    field_name: str,","    values,","    mapping,","    state: dict,","    metadata: dict | None,","    column_index: int,","    input_file_name: str | None,","    logger,","    **_,",") -> list[dict]:"].join(`
`),doc:"Column validator: emit structured issues for a column. Return a list of {row_index, message, ...}.",snippet:`
def validate(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    column_index: int,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Return validation issues for this column.}"""
    issues: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        if metadata and metadata.get("required") and not text:
            issues.append({"row_index": idx, "message": f"{field_name} is required"})
        # Add custom checks here (e.g., regex, enum membership).
    return issues
`.trim(),parameters:["field_name","values","mapping","state","metadata","column_index","input_file_name","logger"]},oe={kind:"hook_workbook_start",name:"on_workbook_start",label:"ADE hook: on_workbook_start",signature:["def on_workbook_start(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called once per workbook before any sheets/tables are processed.",snippet:`
def on_workbook_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Seed shared state or log workbook info.}"""
    state.setdefault("notes", [])
    if logger:
        logger.info("workbook start: %s", input_file_name or "")
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ae={kind:"hook_sheet_start",name:"on_sheet_start",label:"ADE hook: on_sheet_start",signature:["def on_sheet_start(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called when a sheet is selected for processing (before detectors run).",snippet:`
def on_sheet_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Sheet-level logging or state init.}"""
    if logger and sheet:
        logger.info("sheet start: %s", getattr(sheet, "title", ""))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ie={kind:"hook_table_detected",name:"on_table_detected",label:"ADE hook: on_table_detected",signature:["def on_table_detected(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called after a table is detected. Inspect table metadata or log.",snippet:`
def on_table_detected(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Log detection details or tweak state.}"""
    if logger and table:
        logger.info("table detected: sheet=%s header_row=%s", getattr(table, "sheet_name", ""), getattr(table, "header_row_index", None))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},se={kind:"hook_table_mapped",name:"on_table_mapped",label:"ADE hook: on_table_mapped",signature:["def on_table_mapped(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> dict | None:"].join(`
`),doc:"Called after mapping; return a ColumnMappingPatch or None.",snippet:`
def on_table_mapped(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> dict | None:
    """\${1:Propose mapping tweaks or log mapped columns.}"""
    if logger and table:
        mapped = [col.field_name for col in getattr(table, "mapped_columns", [])]
        logger.info("table mapped fields=%s", mapped)
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},ue={kind:"hook_table_written",name:"on_table_written",label:"ADE hook: on_table_written",signature:["def on_table_written(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called after a table is written to the output workbook.",snippet:`
def on_table_written(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Finalize sheet formatting or log counts.}"""
    if logger and table:
        logger.info("table written rows=%s", len(getattr(table, "rows", []) or []))
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},le={kind:"hook_workbook_before_save",name:"on_workbook_before_save",label:"ADE hook: on_workbook_before_save",signature:["def on_workbook_before_save(","    *,","    hook_name,","    metadata: dict | None,","    state: dict,","    workbook,","    sheet,","    table,","    input_file_name: str | None,","    logger,","    **_,",") -> None:"].join(`
`),doc:"Called once before the output workbook is saved to disk.",snippet:`
def on_workbook_before_save(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Style workbook or attach summaries before save.}"""
    if logger:
        logger.info("workbook before save: %s", input_file_name or "")
    return None
`.trim(),parameters:["hook_name","metadata","state","workbook","sheet","table","input_file_name","logger"]},qt=[Ft,Oe,re,ne,oe,ae,ie,se,ue,le],Ut=new Map([[oe.name,oe],[ae.name,ae],[ie.name,ie],[se.name,se],[ue.name,ue],[le.name,le]]);function Ee(e){if(e)return e.startsWith("detect_")?Oe:e===re.name?re:e===ne.name?ne:Ut.get(e)}function Zt(){return qt}const U=new Map;function Gt(e,t="python"){const r=t||"python",n=U.get(r);if(n){n.refCount+=1;return}const o=[Jt(e,r),Qt(e,r),Xt(e,r)];U.set(r,{disposables:o,refCount:1})}function Yt(e="python"){const t=e||"python",r=U.get(t);r&&(r.refCount-=1,r.refCount<=0&&(r.disposables.forEach(n=>n.dispose()),U.delete(t)))}function Jt(e,t){return e.languages.registerHoverProvider(t,{provideHover(r,n){const o=r.getWordAtPosition(n);if(!o)return null;const a=Ee(o.word);return a?{range:new e.Range(n.lineNumber,o.startColumn,n.lineNumber,o.endColumn),contents:[{value:["```python",a.signature,"```"].join(`
`)},{value:a.doc}]}:null}})}function Qt(e,t){const r={suggestions:[]};return e.languages.registerCompletionItemProvider(t,{triggerCharacters:[" ","d","t","_"],provideCompletionItems(n,o){const a=Zt();if(!a||a.length===0)return r;const s=o.lineNumber,u=n.getValueInRange(new e.Range(s,1,s,o.column)),d=u.replace(/\s+$/,""),f=u.length-d.length,v=/[A-Za-z_][\w]*$/.exec(d),_=v?o.column-f-v[0].length:o.column-f,j=new e.Range(s,Math.max(1,_),s,o.column);return{suggestions:a.map((M,S)=>tr(e,M,j,S))}}})}function Xt(e,t){return e.languages.registerSignatureHelpProvider(t,{signatureHelpTriggerCharacters:["(",","],signatureHelpRetriggerCharacters:[","],provideSignatureHelp(r,n){const a=r.getLineContent(n.lineNumber).slice(0,n.column),s=/([A-Za-z_][\w]*)\s*\($/.exec(a);if(!s)return null;const u=Ee(s[1]);if(!u)return null;const d=er(a),f=u.parameters.map(v=>({label:v}));return{value:{signatures:[{label:u.signature,documentation:u.doc,parameters:f}],activeSignature:0,activeParameter:Math.min(Math.max(d,0),Math.max(f.length-1,0))},dispose:()=>{}}}})}function er(e){const t=e.lastIndexOf("(");if(t===-1)return 0;const r=e.slice(t+1);return r.trim()?r.split(",").length-1:0}function tr(e,t,r,n){return{label:t.label,kind:e.languages.CompletionItemKind.Snippet,insertText:t.snippet,insertTextRules:e.languages.CompletionItemInsertTextRule.InsertAsSnippet,documentation:{value:t.doc},detail:t.signature,range:r,sortText:`0${n}`}}const ve="ade-dark",rr={base:"vs-dark",inherit:!0,rules:[],colors:{"editor.background":"#1f2430","editor.foreground":"#f3f6ff","editorCursor.foreground":"#fbd38d","editor.lineHighlightBackground":"#2a3142","editorLineNumber.foreground":"#8c92a3","editor.selectionBackground":"#3a4256","editor.inactiveSelectionBackground":"#2d3446","editorGutter.background":"#1c212b"}},ir=i.forwardRef(function({value:t,onChange:r,language:n="plaintext",path:o,readOnly:a=!1,onSaveShortcut:s,className:u,theme:d=ve},f){const v=i.useRef(s),_=i.useRef(null),j=i.useRef(null),C=i.useMemo(()=>nr(o),[o]),M=i.useRef(null),[S,I]=i.useState(!1);i.useEffect(()=>{v.current=s},[s]);const T=i.useCallback(h=>{r(h??"")},[r]),b=i.useCallback((h,l)=>{const p=h.getModel()?.getLanguageId()??n;p==="python"&&(Gt(l,p),j.current=p),h.addCommand(l.KeyMod.CtrlCmd|l.KeyCode.KeyS,()=>{v.current?.()}),_.current=h,I(!0)},[n]);i.useEffect(()=>()=>{j.current&&(Yt(j.current),j.current=null)},[]),i.useImperativeHandle(f,()=>({focus:()=>{_.current?.focus()},revealLine:h=>{const l=_.current;if(!l)return;const g=Math.max(1,Math.floor(h));l.revealLineInCenter(g),l.setPosition({lineNumber:g,column:1}),l.focus()}}),[]),i.useEffect(()=>{if(!S)return;const h=M.current;if(h&&typeof ResizeObserver<"u"){const g=new ResizeObserver(()=>{_.current?.layout()});return g.observe(h),_.current?.layout(),()=>g.disconnect()}const l=()=>_.current?.layout();return window.addEventListener("resize",l),l(),()=>window.removeEventListener("resize",l)},[S]),i.useEffect(()=>{const h=()=>_.current?.layout();return window.addEventListener("ade:workbench-layout",h),()=>window.removeEventListener("ade:workbench-layout",h)},[]);const x=i.useCallback(h=>{or(),h.editor.defineTheme(ve,rr)},[]);return Q.jsx("div",{ref:M,className:Ce("relative h-full w-full min-w-0 overflow-hidden",u),children:Q.jsx(Wt,{value:t,onChange:T,language:n,path:C,theme:d,beforeMount:x,height:"100%",width:"100%",options:{readOnly:a,minimap:{enabled:!1},fontSize:13,fontFamily:"'JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', monospace",scrollBeyondLastLine:!1,smoothScrolling:!0,automaticLayout:!0,lineNumbersMinChars:3,hover:{enabled:!0},wordBasedSuggestions:"currentDocument",quickSuggestions:{other:!0,comments:!1,strings:!0},suggestOnTriggerCharacters:!0,snippetSuggestions:"inline"},loading:Q.jsx("div",{className:"flex h-full items-center justify-center text-xs text-slate-400",children:"Loading editor…"}),onMount:b})})});function nr(e){return e?e.includes("://")?e:`inmemory://ade/${e.startsWith("/")?e.slice(1):e}`:void 0}function or(){const e=globalThis;e.MonacoEnvironment?.getWorker||(e.MonacoEnvironment={getWorker:(t,r)=>{switch(r){case"json":return new Bt;case"css":case"less":case"scss":return new Ht;case"html":case"handlebars":case"razor":return new Vt;case"typescript":case"javascript":return new Kt;default:return new zt}}})}export{ir as default};
