"""theme.py — 사수 템플릿(seller_persona) 외형을 그대로 옮긴 공용 CSS."""

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CSS = r"""
body{margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;line-height:1.7;color:#333;background:#f5f7fa;}
.entire-UI{max-width:1200px;margin:20px auto;padding:20px;background:#fff;box-shadow:0 0 20px rgba(0,0,0,.1);border-radius:12px;}
.panel-primary{border:1px solid #3b82f6;border-radius:8px;margin-bottom:20px;background:#fff;}
.panel-heading{background:linear-gradient(135deg,#3b82f6,#1d4ed8);color:#fff;padding:18px;font-size:22px;text-align:center;border-radius:8px 8px 0 0;}
.panel-body{padding:18px;} .panel-body h3{margin:18px 0 6px;font-size:16px;}
.highlight-yellow{background:#fef3c7;padding:8px 12px;border-radius:6px;border-left:4px solid #f59e0b;display:inline-block;}
.trait-def-box{background:#f8fafc;border:2px solid #c7d2fe;border-radius:10px;padding:14px 18px;margin:8px 0 12px;}
.trait-def-row{margin-bottom:8px;font-size:14px;line-height:1.6;color:#374151;} .trait-def-row:last-child{margin-bottom:0;}
.trait-def-label{display:inline-block;font-weight:700;color:#4338ca;min-width:150px;vertical-align:top;} .def-text{display:inline-block;max-width:calc(100% - 160px);}
.notice-box{padding:12px 16px;border-radius:8px;margin-top:14px;font-size:13.5px;line-height:1.6;}
.notice-attention{background:#fef2f2;border:1px solid #fca5a5;color:#991b1b;} .notice-research{background:#f0fdf4;border:1px solid #86efac;color:#166534;} .notice-tip{background:#eff6ff;border:1px solid #93c5fd;color:#1e40af;}
#progressBarContainer{width:100%;background:#e5e7eb;margin:10px 0;border-radius:12px;overflow:hidden;}
#progressBar{width:0%;height:22px;background:linear-gradient(90deg,#10b981,#059669);position:relative;transition:width .4s;border-radius:12px;}
#progressPercentage{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:#fff;font-size:12px;font-weight:700;}
#submitButton{background:#d1d5db;color:#6b7280;padding:14px 44px;border:none;border-radius:10px;font-size:17px;font-weight:700;cursor:not-allowed;transition:all .3s;}
.btn-enabled{background:linear-gradient(135deg,#3b82f6,#1d4ed8)!important;color:#fff!important;cursor:pointer!important;box-shadow:0 4px 10px rgba(59,130,246,.3);}
#tabBar{display:flex;flex-wrap:wrap;gap:4px;border-bottom:2px solid #e5e7eb;margin-bottom:14px;}
.tab-btn{background:#f8fafc;border:1px solid #e5e7eb;border-bottom:none;border-radius:8px 8px 0 0;padding:8px 14px;font-size:13.5px;font-weight:600;color:#475569;cursor:pointer;}
.tab-btn.active{background:#fff;color:#1e40af;border-color:#3b82f6;box-shadow:0 -2px 0 #3b82f6 inset;} .tab-btn.done::after{content:' \2713';color:#10b981;}
.tab-inner{padding:4px 0;display:flex;flex-direction:column;gap:18px;}
.tab-title{color:#1e40af;font-size:19px;font-weight:700;margin:0;padding-bottom:8px;border-bottom:2px solid #3b82f6;}
.prod-card{border:2px solid #e5e7eb;border-radius:14px;overflow:hidden;} .prod-hdr{background:linear-gradient(135deg,#6366f1,#4f46e5);color:#fff;padding:10px 18px;font-weight:600;font-size:15px;} .prod-body{padding:14px 18px;}
.ctx-query{font-size:16px;font-weight:600;color:#1e293b;} .ctx-sub{margin-top:8px;} .info-k{font-size:.73rem;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:.4px;}
.scripts-side-by-side{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;}
.script-card{border:2px solid #e5e7eb;border-radius:14px;overflow:hidden;} .script-card-a{border-color:#f9a8d4;} .script-card-b{border-color:#93c5fd;}
.script-hdr{color:#fff;padding:10px 16px;font-weight:700;font-size:15px;text-align:center;} .script-card-a-hdr{background:linear-gradient(135deg,#ec4899,#db2777);} .script-card-b-hdr{background:linear-gradient(135deg,#3b82f6,#2563eb);}
.script-body{padding:14px 18px;font-size:14px;line-height:1.75;color:#1f2937;word-wrap:break-word;max-height:460px;overflow-y:auto;background:#fafbfc;}
.num-list{margin:0;padding-left:0;list-style:none;} .num-list li{margin:6px 0;display:flex;gap:8px;align-items:flex-start;}
.chk-idx{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;border-radius:6px;background:#e0e7ff;color:#3730a3;font-size:12px;font-weight:800;flex:0 0 auto;margin-top:3px;}
.comp-section{border:2px solid #8b5cf6;border-radius:14px;overflow:hidden;} .comp-section-hdr{background:linear-gradient(135deg,#8b5cf6,#7c3aed);color:#fff;padding:12px 20px;font-weight:700;font-size:16px;text-align:center;}
.comp-card{background:#faf5ff;padding:16px 20px;}
.chk-list{display:flex;flex-direction:column;gap:8px;} .chk-opt{display:flex;gap:10px;align-items:flex-start;background:#fff;border:2px solid #e5e7eb;border-radius:10px;padding:10px 14px;cursor:pointer;font-size:14px;line-height:1.55;transition:all .15s;}
.chk-opt:hover{border-color:#c4b5fd;} .chk-opt.chk-sel{border-color:#7c3aed;background:#f5f3ff;} .chk-opt input{margin-top:5px;} .chk-none{border-style:dashed;color:#6b7280;} .chk-none.chk-sel{border-color:#dc2626;background:#fef2f2;color:#991b1b;}
.sq-block{background:#fff;border:2px solid #ddd6fe;border-radius:12px;padding:14px 16px;margin-bottom:14px;} .sq-title{font-size:.8rem;font-weight:800;color:#6d28d9;text-transform:uppercase;letter-spacing:.4px;} .sq-text{font-size:15px;font-weight:600;color:#1e293b;margin:4px 0 10px;} .sq-q{font-size:13.5px;font-weight:600;color:#374151;margin:12px 0 8px;}
.ab-row{display:flex;justify-content:center;gap:16px;flex-wrap:wrap;} .ab-opt{cursor:pointer;} .ab-opt input[type=radio]{display:none;}
.ab-btn{display:inline-block;padding:10px 34px;border-radius:10px;font-weight:700;font-size:15px;border:2px solid #d1d5db;transition:all .2s;color:#374151;background:#f9fafb;}
.ab-btn-a{border-color:#86efac;color:#166534;background:#f0fdf4;} .ab-btn-b{border-color:#fca5a5;color:#991b1b;background:#fef2f2;}
.ab-opt.ab-sel .ab-btn-a{background:#16a34a;color:#fff;border-color:#16a34a;} .ab-opt.ab-sel .ab-btn-b{background:#dc2626;color:#fff;border-color:#dc2626;}
.chunk-details{margin-top:10px;font-size:13px;} .chunk-details summary{cursor:pointer;color:#4338ca;font-weight:600;} .mini-chunk{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;margin-top:6px;}
#previewOut{display:none;margin-top:20px;background:#0f172a;color:#e2e8f0;border-radius:10px;padding:14px;} #previewOut pre{margin:0;white-space:pre-wrap;font-size:12px;}
.preview-banner{background:#fff7ed;border:1px solid #fdba74;color:#9a3412;padding:8px 14px;border-radius:8px;font-size:13px;margin-bottom:12px;}
@media(max-width:768px){.entire-UI{margin:10px;padding:14px;}.scripts-side-by-side{grid-template-columns:1fr;}.trait-def-label{min-width:0;display:block;}.def-text{max-width:100%;}}
"""
