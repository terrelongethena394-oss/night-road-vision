"""Dark desktop workbench for the verified local photo-to-board workflow."""
from pathlib import Path
import os,queue,sys,threading
import tkinter as tk
from tkinter import filedialog,messagebox
from PIL import Image,ImageOps
sys.path.insert(0,'E:/FPGA_Enhance_Work/photo_ui_lib')
import customtkinter as ctk
from photo_station_core import DELIVERY,RESULT_ROOT,STAGING,process_photo
from camera_station_core import preview,process_camera
from car_roi_delivery_common import read,write

BG='#0B1018';SURFACE='#121B28';BORDER='#253244';VIEW='#090E16'
TEXT='#EDF4FC';MUTED='#8192A8';ACCENT='#69E3C0';INK='#092B24'
FONT='Microsoft YaHei UI'

def font(size=13,weight='normal'):
    return ctk.CTkFont(family=FONT,size=size,weight=weight)

class PreviewCard(ctk.CTkFrame):
    def __init__(self,parent,title,eyebrow,index,overlay=None):
        super().__init__(parent,fg_color=SURFACE,border_color=BORDER,border_width=1,corner_radius=20)
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        self.base=None;self.source_path=None;self.image=None;self.resize_job=None
        header=ctk.CTkFrame(self,fg_color='transparent');header.grid(row=0,column=0,sticky='ew',padx=22,pady=(19,15));header.columnconfigure(1,weight=1)
        ctk.CTkLabel(header,text=index,width=30,height=30,fg_color='#1C2A3B',corner_radius=9,text_color='#A4B6CE',font=font(11,'bold')).grid(row=0,column=0,rowspan=2,padx=(0,12))
        ctk.CTkLabel(header,text=title,text_color=TEXT,font=font(17,'bold'),anchor='w').grid(row=0,column=1,sticky='w')
        ctk.CTkLabel(header,text=eyebrow,text_color=MUTED,font=font(9),anchor='w').grid(row=1,column=1,sticky='w')
        self.count=ctk.CTkLabel(header,text='',text_color=ACCENT,font=font(11));self.count.grid(row=0,column=2,sticky='e')
        if overlay is not None:
            self.toggle=ctk.CTkSwitch(header,text='识别框',variable=overlay[0],command=overlay[1],width=92,height=18,switch_width=28,switch_height=16,
                progress_color=ACCENT,button_color='#E5FFF7',button_hover_color='#FFFFFF',fg_color='#344258',text_color=MUTED,font=font(11))
            self.toggle.grid(row=1,column=2,sticky='e',pady=(3,0))
        self.viewport=ctk.CTkFrame(self,fg_color=VIEW,corner_radius=12,height=290)
        self.viewport.grid(row=1,column=0,sticky='nsew',padx=14,pady=(0,14))
        self.placeholder=ctk.CTkFrame(self.viewport,fg_color='transparent');self.placeholder.place(relx=.5,rely=.5,anchor='center')
        ctk.CTkLabel(self.placeholder,text='＋' if index=='01' else '↗',font=font(32),text_color='#3C5B70').pack(pady=(0,8))
        self.prompt=ctk.CTkLabel(self.placeholder,text='选择照片，在这里预览' if index=='01' else '等待图像处理结果',font=font(12),text_color='#62748C');self.prompt.pack()
        self.label=ctk.CTkLabel(self.viewport,text='',fg_color='transparent')
        self.viewport.bind('<Configure>',self.schedule)

    def schedule(self,event=None):
        if self.resize_job is not None:self.after_cancel(self.resize_job)
        self.resize_job=self.after(70,self.render)

    def render(self):
        self.resize_job=None
        if self.base is None:return
        w=max(40,self.viewport.winfo_width()-20);h=max(40,self.viewport.winfo_height()-20)
        scale=min(w/self.base.width,h/self.base.height)
        size=(max(1,int(self.base.width*scale)),max(1,int(self.base.height*scale)))
        self.image=ctk.CTkImage(light_image=self.base,dark_image=self.base,size=size)
        self.label.configure(image=self.image,text='');self.placeholder.place_forget();self.label.place(relx=.5,rely=.5,anchor='center')

    def show(self,path):
        with Image.open(path) as im:self.base=ImageOps.exif_transpose(im).convert('RGB').copy()
        self.source_path=Path(path);self.schedule()

    def clear(self):
        # CTkLabel 5.2.2 does not clear its native Tk image when passed None.
        # Keep the hidden image alive until the next render replaces it.
        self.base=None;self.source_path=None;self.label.place_forget()
        self.placeholder.place(relx=.5,rely=.5,anchor='center');self.count.configure(text='')

class PhotoStation:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.busy=False;self.close_after=False;self.input=None;self.result=None
        self.mode='照片';self.previewing=False;self.preview_stop=threading.Event();self.pending_capture=False
        root.title('夜视工作台 · 图像增强与汽车识别');root.geometry('1120x750');root.minsize(980,650);root.configure(fg_color=BG)
        outer=ctk.CTkFrame(root,fg_color='transparent');outer.pack(fill='both',expand=True,padx=30,pady=(25,20));outer.columnconfigure(0,weight=1);outer.rowconfigure(3,weight=1)
        top=ctk.CTkFrame(outer,fg_color='transparent');top.grid(row=0,column=0,sticky='ew',pady=(0,24));top.columnconfigure(1,weight=1)
        ctk.CTkLabel(top,text='NV',width=39,height=39,corner_radius=12,fg_color=ACCENT,text_color=INK,font=font(14,'bold')).grid(row=0,column=0,rowspan=2,padx=(0,12))
        ctk.CTkLabel(top,text='夜视工作台',text_color=TEXT,font=font(16,'bold'),anchor='w').grid(row=0,column=1,sticky='w')
        ctk.CTkLabel(top,text='NIGHT VISION STUDIO',text_color='#60758D',font=font(9),anchor='w').grid(row=1,column=1,sticky='w')
        self.badge=ctk.CTkLabel(top,text='●  待处理',width=100,height=30,corner_radius=15,fg_color='#182534',text_color='#9CAEC2',font=font(11))
        self.badge.grid(row=0,column=2,rowspan=2,sticky='e')
        hero=ctk.CTkFrame(outer,fg_color='transparent');hero.grid(row=1,column=0,sticky='ew',pady=(0,20))
        ctk.CTkLabel(hero,text='暗光图像处理',text_color=TEXT,font=font(29,'bold'),anchor='w').pack(anchor='w')
        ctk.CTkLabel(hero,text='原图对照  /  图像增强  /  汽车识别',text_color=MUTED,font=font(12),anchor='w').pack(anchor='w',pady=(5,0))
        self.source_selector=ctk.CTkSegmentedButton(hero,values=['照片','摄像头'],command=self.change_source,font=font(12),height=32,
            fg_color='#182534',selected_color='#2B564E',selected_hover_color='#35685D',unselected_color='#182534',unselected_hover_color='#26394D')
        self.source_selector.set('照片');self.source_selector.pack(anchor='w',pady=(14,0))
        toolbar=ctk.CTkFrame(outer,fg_color=SURFACE,border_color=BORDER,border_width=1,corner_radius=18)
        toolbar.grid(row=2,column=0,sticky='ew',pady=(0,20));toolbar.columnconfigure(1,weight=1)
        self.file_icon=ctk.CTkLabel(toolbar,text='IMG',width=46,height=46,corner_radius=12,fg_color='#1D2C3E',text_color='#B2C7DD',font=font(11,'bold'))
        self.file_icon.grid(row=0,column=0,rowspan=2,padx=(18,13),pady=17)
        self.file_name=ctk.CTkLabel(toolbar,text='添加你的夜间照片',text_color=TEXT,font=font(13,'bold'),anchor='w');self.file_name.grid(row=0,column=1,sticky='sw',pady=(16,1))
        self.file_hint=ctk.CTkLabel(toolbar,text='JPG · PNG · BMP · WebP',text_color=MUTED,font=font(10),anchor='w');self.file_hint.grid(row=1,column=1,sticky='nw',pady=(0,15))
        self.choose=ctk.CTkButton(toolbar,text='＋ 选择照片',width=114,height=40,corner_radius=10,fg_color='#1B2A3D',hover_color='#263B52',text_color='#D5E3F1',border_width=1,border_color='#31445B',font=font(12),command=self.choose_source)
        self.choose.grid(row=0,column=2,rowspan=2,padx=(10,8))
        self.open=ctk.CTkButton(toolbar,text='查看结果',width=94,height=40,corner_radius=10,fg_color='transparent',hover_color='#203146',text_color='#A7BDCF',font=font(12),command=self.open_results)
        self.open.grid(row=0,column=3,rowspan=2,padx=(0,8))
        self.process=ctk.CTkButton(toolbar,text='开始处理  →',width=145,height=42,corner_radius=11,fg_color=ACCENT,hover_color='#91F1D4',text_color=INK,text_color_disabled='#526A68',font=font(13,'bold'),command=self.begin,state='disabled')
        self.process.grid(row=0,column=4,rowspan=2,padx=(0,18))
        cards=ctk.CTkFrame(outer,fg_color='transparent');cards.grid(row=3,column=0,sticky='nsew');cards.columnconfigure(0,weight=1,uniform='images');cards.columnconfigure(1,weight=1,uniform='images');cards.rowconfigure(0,weight=1)
        self.show_boxes=tk.BooleanVar(value=True)
        self.raw=PreviewCard(cards,'原图','ORIGINAL IMAGE','01');self.raw.grid(row=0,column=0,sticky='nsew',padx=(0,9))
        self.enh=PreviewCard(cards,'增强与识别','ENHANCED RESULT','02',(self.show_boxes,self.refresh_result));self.enh.grid(row=0,column=1,sticky='nsew',padx=(9,0))
        footer=ctk.CTkFrame(outer,fg_color='transparent');footer.grid(row=4,column=0,sticky='ew',pady=(15,0));footer.columnconfigure(0,weight=1)
        self.status=ctk.CTkLabel(footer,text='请选择照片开始',text_color=MUTED,font=font(11),anchor='w');self.status.grid(row=0,column=0,sticky='w')
        self.progress=ctk.CTkProgressBar(footer,width=175,height=3,corner_radius=2,mode='indeterminate',fg_color='#1B2A3A',progress_color=ACCENT)
        self.progress.grid(row=0,column=1,sticky='e');self.progress.grid_remove()
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)
        previous=STAGING/'gui_last_result.json'
        if not previous.exists():previous=STAGING/'actual_roundtrip_verified.json'
        if previous.exists():
            r=read(previous)
            if Path(r['output']).is_dir():
                if r.get('source_kind')=='camera':
                    self.source_selector.set('摄像头');self.change_source('摄像头')
                else:
                    p=Path(r['input']['original_path'])
                    if p.is_file():self.set_input(p)
                self.display_result(r,previous=True)
        self.controls()

    def controls(self):
        self.source_selector.configure(state='disabled' if self.busy or self.previewing else 'normal')
        self.choose.configure(state='disabled' if self.busy else 'normal',text=('停止取景' if self.previewing else '开启取景') if self.mode=='摄像头' else '＋ 选择照片')
        self.process.configure(state='disabled' if self.busy or (self.mode=='照片' and self.input is None) else 'normal',text='抓拍处理  →' if self.mode=='摄像头' else '开始处理  →')
        self.open.configure(state='disabled' if self.busy else 'normal')

    def change_source(self,value):
        if self.busy or self.previewing:return
        self.mode=value;self.result=None;self.enh.clear();self.raw.clear()
        if value=='摄像头':
            self.raw.prompt.configure(text='开启取景，在这里调整构图')
            self.file_icon.configure(text='CAM');self.file_name.configure(text='OV5640 摄像头')
            self.file_hint.configure(text='取景构图 → 抓拍单帧 → 增强与识别')
            self.status.configure(text='开启取景后，点击抓拍处理');self.badge.configure(text='●  摄像头',text_color=ACCENT)
        else:
            self.raw.prompt.configure(text='选择照片，在这里预览')
            if self.input:self.set_input(self.input)
            else:self.file_name.configure(text='添加你的夜间照片');self.file_icon.configure(text='IMG');self.file_hint.configure(text='JPG · PNG · BMP · WebP')
            self.status.configure(text='请选择照片开始');self.badge.configure(text='●  待处理',text_color=MUTED)
        self.controls()

    def choose_source(self):
        if self.mode=='照片':self.pick()
        elif self.previewing:
            self.preview_stop.set();self.choose.configure(state='disabled');self.status.configure(text='正在结束本次取景…')
        else:self.start_preview()

    def start_preview(self):
        if self.busy or self.previewing:return
        self.preview_stop=threading.Event();self.previewing=True;self.result=None;self.enh.clear();self.raw.clear();self.controls()
        self.status.configure(text='正在连接摄像头…');self.badge.configure(text='●  取景中',text_color=ACCENT)
        def worker():
            error=None
            try:preview(self.preview_stop,lambda frame:self.events.put(('frame',frame)),notify=lambda text:self.events.put(('camera_status',text)))
            except Exception as e:error=str(e)
            self.events.put(('preview_done',error))
        threading.Thread(target=worker,daemon=False).start()

    def set_input(self,path):
        path=Path(path);self.raw.show(path);self.input=path
        name=path.name;self.file_name.configure(text=name if len(name)<32 else name[:18]+'…'+name[-10:])
        self.file_icon.configure(text=path.suffix.lstrip('.').upper()[:4] or 'IMG')
        self.file_hint.configure(text='已选择照片');self.process.configure(state='normal')

    def pick(self):
        path=filedialog.askopenfilename(parent=self.root,title='选择夜间照片',initialdir=str(DELIVERY/'示例照片'),filetypes=[('照片','*.jpg *.jpeg *.png *.bmp *.webp'),('所有文件','*.*')])
        if not path:return
        try:
            self.set_input(path);self.result=None;self.enh.clear();self.status.configure(text='照片已就绪');self.badge.configure(text='●  待处理',text_color='#A5B6CB')
        except Exception as e:messagebox.showerror('无法打开照片',str(e),parent=self.root)

    def begin(self):
        if self.busy or (self.mode=='照片' and self.input is None):return
        if self.previewing:
            self.pending_capture=True;self.preview_stop.set();self.choose.configure(state='disabled');self.process.configure(state='disabled')
            self.status.configure(text='正在固定摄像头画面…');return
        self.busy=True;self.choose.configure(state='disabled');self.process.configure(state='disabled');self.open.configure(state='disabled');self.progress.grid();self.progress.start()
        self.controls();self.badge.configure(text='●  处理中',text_color='#89B9F4');self.status.configure(text='正在抓拍并处理，约需半分钟…' if self.mode=='摄像头' else '正在准备照片…')
        def worker():
            try:
                notify=lambda text:self.events.put(('status',text))
                result=process_camera(notify=notify) if self.mode=='摄像头' else process_photo(self.input,notify=notify)
                self.events.put(('done',result))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=False).start()

    def refresh_result(self):
        if self.result:
            out=Path(self.result['output']);self.enh.show(out/('05_增强显示与汽车框.png' if self.show_boxes.get() else '03_板上增强400.png'))

    def display_result(self,result,previous=False):
        self.result=result;out=Path(result['output'])
        self.raw.show(out/'02_板上原图400.png');self.refresh_result();self.enh.count.configure(text=f"{result['car_count']} 个目标")
        status='上次处理结果' if previous else ('抓拍处理完成 · 可再次开启取景' if result.get('source_kind')=='camera' else '处理完成')
        if result.get('enhancement_profile')=='natural_exposure_guard55':status+=' · 自然增强'
        self.status.configure(text=status);self.badge.configure(text='●  已完成',text_color=ACCENT)
        self.open.configure(state='normal')
        if not previous:write(STAGING/'gui_last_result.json',result)

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='frame':
                    if Path(value['path']).exists():self.raw.show(value['path'])
                    self.status.configure(text='摄像头取景中 · 电脑定时更新');continue
                if kind=='camera_status':self.status.configure(text=value);continue
                if kind=='preview_done':
                    self.previewing=False;pending=self.pending_capture;self.pending_capture=False;self.controls()
                    if self.close_after:self.root.destroy();return
                    if value:
                        self.status.configure(text='取景未完成');self.badge.configure(text='●  请检查连接',text_color='#F1AA96')
                        messagebox.showerror('摄像头连接',value,parent=self.root)
                    elif pending:self.begin()
                    else:
                        self.status.configure(text='取景已停止，可抓拍处理或重新取景');self.badge.configure(text='●  待抓拍',text_color=MUTED)
                    continue
                if kind=='status':
                    if value.startswith('正在读取'):text='正在准备照片…'
                    elif value.startswith('正在加载'):text='正在初始化开发板…'
                    elif value.startswith('已连接'):text='开发板已就绪'
                    elif value.startswith('正在上传'):text='正在处理照片，请稍候…'
                    elif value.startswith('正在抓拍'):text='正在处理抓拍，请稍候…'
                    elif value.startswith('结果已回传'):text='正在保存结果…'
                    else:text='正在处理…'
                    self.status.configure(text=text)
                else:
                    self.busy=False;self.progress.stop();self.progress.grid_remove();self.controls()
                    if kind=='done':self.display_result(value)
                    else:
                        self.status.configure(text='处理未完成');self.badge.configure(text='●  请检查连接',text_color='#F1AA96')
                        if not self.close_after:messagebox.showerror('处理未完成',value,parent=self.root)
                    if self.close_after:self.root.destroy();return
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def open_results(self):
        path=Path(self.result['output']) if self.result else RESULT_ROOT;path.mkdir(parents=True,exist_ok=True);os.startfile(path)

    def close(self):
        if self.busy or self.previewing:self.close_after=True;self.preview_stop.set();self.pending_capture=False;self.root.withdraw()
        else:self.root.destroy()

def main():
    ctk.set_appearance_mode('dark');ctk.set_default_color_theme('dark-blue')
    root=ctk.CTk();PhotoStation(root);root.mainloop()

if __name__=='__main__':main()
