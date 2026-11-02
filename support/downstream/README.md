# 2026-10-23 新任务：增强前后数字识别对比

## 2026-10-26 13:25 新任务进行中：用户要求持续完善识别器，离线通过后再上板

最新用户明确“继续，一直做，等你完善好再上板验证”。已承诺先做电脑端模型/回归验证，通过才部署；**当前不连接/下载/改板卡和SD**，仍运行旧v6评估版。不能只给计划或中途结束等继续。不要部署之前拒收的robust/preserved_candidate权重。

目前重点修识别器domain gap：旧SVHN original26731 CNN officialTEST仅85.1644%，3门牌正常1/3，人工暗化0/6。新目录 **E:/FPGA_Enhance_Work/recognition_upgrade_20261026/**，计划保持conv1(1->8)/conv2(8->16)与28灰度，fc1扩至64（约52179参数，MAC只增8%）；先验证ROI对比度标准化，再以旧模型为教师保持SVHN能力，混合多字体、MNIST、真实Chars74K和已有raw/NN8/Multinex train views。正常/暗光识别收益与增强收益分开统计。必须新权重位宽/NumPy-C/ARM logits重新核对。

已发现本机MNIST完整train/test gzip、SVHN TRAIN73257（原train65257/val8000）、TEST26032缓存。robust train_views有4253*6、val523*6，均为既有train/val，不用其已拒收权重。Windows Latin可用30字体家族约170文件；拟按家族分train22/val4/test4，不能字体变体泄漏，不复制分发Windows原font文件。MNIST TRAIN再划54k/6k，TEST只最终评测。新ROI normalization拟固定P5/P95 nearest-rank，span>=32，以192/span居中到128，整数round-away，三个view相同处理；输入仍uint8 28x28。

正在从作者官方Chars74K页公开Drive链接下载EnglishImg128MB、Maps1.3MB、Lists7MB：script fetch_chars74k_upgrade.py，active exec **session85529**，log E:/FPGA_Enhance_Work/chars74k_download_20261026.log。作者页https://teodecampos.github.io/chars74k/有download要求引用deCampos/Babu/Varma VISAPP2009，下载地址已web读取验证；Maps公开download200 gzip成功，script安全检查tar普通文件/路径范围，不提取symlink。下一步解析Maps把同一原始场景的char分同组，再冻结训练/验证/测试；尚未生成训练协议或开始训练。作者官方来源已浏览，如最终提及此数据集须用Markdown链接引用。

现有街景val/字体val用于选checkpoint，独立font家族test/真实Chars74K scene test和官方SVHNtest用于最终检查；已看过3门牌只做明确标注的回归，不可宣称新盲测或挑成功图。用户希望真实改善，若初候选不达标继续修，在没有验证前不急上板。

## 2026-10-26 13:10 最终：识别对比版已接通/上板/封存，计算通过但识别效果未接收

当前板上 **E:/FPGA_Enhance_Work/multinex_camera_digit_fast_20261026/** v6，同r4d bit/PS/BSP（没有新增PL识别器），图像增强在PL、同一冻结26731参数数字CNN复用在ARM#0，RAW识别与PL任务重叠，NET与AUTO之后，同tensor复用分数。屏幕左右同绿色ROI，左RAW/右保护图；底部RAW/NET/AUTO三路预测，不是三套权重。默认live ROI(144,64,112)，class10显示'-'；没有自动定位/物品识别/车牌OCR，无数字不保证都能拒绝。

完整闭环已做：219输入/2409logits C对NumPy精确；old C64和new i32均通过；编译→JTAG→13项原照片/亮度/控制输入→13项全部模型输出、保护、ROI灰度、33scores、预测、LCD框与数字字形全精确→live_snapshot再同项确认→恢复连续摄像头。合计14帧1,344,000像素增强/保护校验，32928灰度字节与462logits。10.286秒82次更新，**7.9720008Hz**，DMA无错误。RAW分类约6.6~7.7ms、其余约6.9~13.4ms；核仍约79ms，真实速度已记录，不称30FPS或全部CNN在FPGA。

**识别准确率未通过/不够可靠，不能隐瞒：**三张之前看过的Wikimedia门牌（8/5/8）原亮度RAW1/3、NET0/3、AUTO1/3；同图乘.25/.125各三项均0/3。9变体不等于9独立场景，不是真实暗光/新盲测。NET比RAW多损失1个正确，无新增正确，AUTO保持RAW的1个正确，不能宣称增强稳定提升识别率。当前作为识别比较评测工具保留，不是成熟识别演示。权重仍原074785...，没有用此前被拒收训练候选，没有真值/标签传板、没有挑正确案例或硬编码数字。

状态board_deployed.json为RECOGNITION_COMPARISON_BUILD_NUMERICALLY_VERIFIED、recognizer_accuracy_accepted=false。入口 **识别对比验证结果.md**。恢复包 **E:/FPGA_Enhance_Work/multinex_digit_comparison_verified_20261026.zip**，SHA256 **0bc0eea58b890e22a19dffc694f1b612b83300a41299ab0e0ac58bb1875cc1a9**，CRC通过。当前live正在运行；旧增强保护版zip和其他旧版保留，SD未改。actual_lcd_ddr.png直接DDR回读，不是屏幕拍照；已查看门牌5正常光RAW5/NET2/AUTO5的实际标签和图。

下一步优先改进识别器与真实数据，指南starter/downstream/识别下一步数据与训练安排.md（3人分工、按物体/会话划分、RAW/NET/AUTO同组、真实无数字背景、正常光保持、独立暗光验证）。不要只换权重就上板：必须重做位宽证明/全logits核对。本轮实做连接功能已完整结束，接下来不能把计算路径成功当准确率成功。

## 2026-10-26 12:58 当前新任务：接回同权重数字识别，ARM版已验证，i32等价加速版正在下载

用户在上一版完成后问“现在有识别吗”，已如实答没有；随后问“下一步要做什么”。结合持续自主授权，已开始并实做独立识别接入，不只给计划。增强仍在PL，识别用ARM#0原26731参数CNN（非拒收的保持训练候选），model pth SHA **07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493**。同帧RAW/纯NET/AUTO三路、同ROI、同权重；只做给定区域单数字0..9加background10，不自动定位/物品或车牌OCR。

原native C kernel `digit_arm_reference_20261026` 219个训练数值样本+控制共2409logits逐值匹配独立NumPy（不是新准确率测试）。初版运行 **multinex_camera_digit_20261026** v6：13固定输入已全部捕获、base增强/保护/屏幕含框核对与分类gray/logits/UI数字验证已完成全部（日志session13584返回完成）；正常门牌5 RAW5/NET2/AUTO5，另两张8多错认；暗化照片未见稳定识别收益，不得掩盖。RAW识别约10~11.6ms与PL79ms重叠，NET/AUTO其余约10~21ms；同tensor复用仍逐路对照验证。尚未封存该初版。

新版 **E:/FPGA_Enhance_Work/multinex_camera_digit_fast_20261026/** i32等价优化编译641468B，当前JTAG start工具session请看最新返回，日志jtag_start.log，**未核对成功前不能声称新版本已通过**。参考`digit_arm_reference_i32_20261026`又通过219/2409精确。保守绝对“加权和+偏置”范围保证每个前缀/单乘积：conv1 5292720 /1008270，conv2 44185365/3191300，fc1 1985892096/33185250 均安全int32；fc2 7918482945/2288477136必须int64。classifier_width_proof.json保存证明，权重/舍入/激活不变；同bit/PS/BSP，无PL增加资源。

代码：digit_arm_kernel.h纯C、digit_camera_adapter.h（28x28、灰度77/150/29；ROI边长28倍数平均池化）、main宏DIGIT_RECOGNITION1。prepare_multinex_camera.py recognition_fast编译独立目录，明示ARM识别不冒充FPGA识别。主屏左右绿色同ROI，底部RAW/NET/AUTO分类结果（background10画'-'）。默认live ROI x144 y64 size112；host可传独立人工ROI，真实live恢复默认。RAW在PL工作期间识别，NET/AUTO之后；如果AUTO灰度张量完全等于RAW或NET则复用logits/标签，physicalevals2，否则3，不做标签挑选。

v6邮箱magic0x4D584334，新增38RAWpred/39NETpred/40AUTOpred，41/42RAWticks，43/44othersTicks，45evals，46ROI_x/47y/48size，49grayAddr(0x04E00000)/50scoreAddr(0x04E01000)/51digitver1/52digitseq。灰度3*784B和logits3*11*signed64仅CPU用，CMD1暂停前flush8192B供JTAG。M_D_SEQ==frameSEQ。CMD2注入照片仍先invalidate输入，三个分支同一帧无truth送板。

输入13项已冻结且fast目录rebase相同SHA：三张原始Wikimedia完整照片（8/5/8），整张等比letterbox800x480→RGB565零扩展→2x2均值400x240；原先人工crop映射ROI向28倍数取整；每张gain1/.25/.125，另黑/白/灰40/随机控制。保留完整照片上下文无数字重新粘贴，但有黑色letterbox；暗化是人工非真实夜景/照度；3张照片衍生9张不是9个独立场景，也不是新盲测。sources/attribution已复制，truth仅hostJSON不送到ARM。不得根据识别结果挑成功照片。

接下来自动：start成功→test_digit_camera.tcl13项(约2~3分钟JTAG)→validate_digit_camera.py各目录(包含base增强验证、ROI灰度、33logits、预测和实际LCD数字字形)→live_snapshot/validate→measure cadence→汇总错例与小样本成绩/保存恢复包。新输入仍在sameframe400x240，旧增强包/SD不改。若JTAG FTDI错误可依前次具体核对本会话自动hwserver再重启，不能杀无关进程；若物理掉线需请用户。

## 2026-10-26 11:48 最终：摄像头画质保护快版完成验证/上板/封存，当前live约8.51Hz

当前板上 **E:/FPGA_Enhance_Work/multinex_camera_protected_fast_20261026/**，邮箱magic0x4D584334/version5，SD未写。FTDI一次io错误后直接重试卡在下载服务；已仅停止本会话rdi_xsct24292和自动hw_server46752（先核对进程/命令），新服务自动重启恢复，无需用户拔线，随后成功下载并完整核对。旧cached_v4/r4dstatic版本zip保持。

**已完成本轮，不再等用户喊“继续”**：照片quality规则验证/已有20对回归→新ARM→JTAG→三个host照片分支alpha0、224、256→每个96000像素PL纯输出/保护结果/LCD逐字节一致→恢复live→live_snapshot真实摄像头96000像素input对capture2x2/模型输出/保护/LCD全部精确→持续10.340秒88次更新**8.5106383Hz**，DMA0错误。v4未保护9.313Hz作参考，当前稍慢，不能继续声称9.3或30FPS。网络79ms仍运行，即使KEEP也跑纯网络便于审核；未实现正常光跳过网络，不得假称节能或20Hz。当前帧normalmean75 alpha0标题KEEP，左右原图相同是正常光保护生效。

质量策略meanY≤32 alpha256、≥48 alpha0，中间alpha=((48-Y)*256+8)//16；32/48只由原验证12对选择。ARM保护独立于原696参数网络，权重/bit未变。原纯OUTPUT0x04200000保留，FINAL0x04C00000为保护后右显示。等价加速R/B双lane打包计算已由alpha224实板逐像素验证；FINAL仅CPU使用，调试暂停前flush供JTAG。Mailbox34:Y/35:alpha/36:FINAL/37:SOURCE，SOURCE1=host photo，0=camera，CMD2用于注入照片后处理并自动暂停，CMD0恢复live。

**质量成绩边界**：匹配camera400x240/RGB565/2x2的20对既有回归（只有10个不同正常GT，已看过、非全新盲测）：暗光原图PSNR10.168/SSIM.2444；旧NN8 18.597/.6823；纯Mult18.570/.8276；保护后18.731/.8293（19全增强、low00729 mean34 alpha224）。正常20均完全保持输入，不再过增亮；相对理想未量化GT SSIM.99096，不能当神经网络本体大幅变强。没有新的识别率/独立实拍噪声/照明切换或视频闪烁证据，后续需要这些。用户不方便布置灯光，选择先用已有照片，故未要求再次摆灯拍照。

入口 **画质保护版结果.md**、board_deployed.json；恢复包 **E:/FPGA_Enhance_Work/multinex_camera_quality_verified_20261026.zip**，SHA256 **92a14a81c270da8e4867a8e341b5ab959ea7197b0c544329fd8d7622f6856894**，CRC通过。report区分PC数据集成绩与四项真正实板帧，host照片status ACTUAL_HOST_PHOTO_ENHANCEMENT_EXACT，不冒充摄像头。live_snapshot actual_lcd_ddr.png来自真实DDR，已查看，非LCD拍照。

后续若用户继续：优先独立暗光实拍/噪声和曝光切换稳定性或同一识别器的原图/纯增强/保护后对比，不能再用已拒收的识别训练候选或宣称普遍识别收益；保留SD不写约束。用户此前要求自主完成到上板，本轮完整闭环已完成，可以报告结果，无需询问“要不要继续”。

## 2026-10-26 11:39 最新：保护v5三分支+live正确，但约8Hz；等价加速版下载遇FTDI错误，正在一次重试

**multinex_camera_protected_20261026** 已实板三张原有照片alpha256/0/224共288000像素：纯PL输出对冻结C++、ARM保护输出对独立公式、LCD同帧两侧全精确；随后恢复live，live_snapshot再96000像素/capture均值/保护/LCD全精确，camera_source标志0。snapshot live均值35 alpha208，模型78.75ms，但额外保护使10.351秒83次更新约8.02Hz，DMA0，不能说仍9.3Hz。

为保持用户已接受的流畅度，准备独立 **E:/FPGA_Enhance_Work/multinex_camera_protected_fast_20261026/**，新ARM581228B，同bit/策略；prepare_multinex_camera.py protected_fast。仅等价优化：alpha0/256 memcpy；混合用R/B双16bit lane打包乘法（每lane<=65408<65536，防进位），G独立；FINAL只供CPU显示，不再每帧flush，调试CMD1暂停前再flush给JTAG。输入/模型输出/LCD/capture原缓存维护不变，数学公式原样。

新优化版第一次JTAG在fpga步骤FT_Write failed: io error，日志jtag_start_attempt1_usb_error.log，APU已识别但下载失败，可能已重置/屏幕空白；已向用户说明下载器USB一次错误、保持供电接线勿动。当前自动重试一次，session95300，新root/jtag_start.log；尚未成功启动前不能执行照片测试。若重试仍失败则必须请用户重插独立JTAG下载器USB，不要无效重复尝试。不要写SD。

下一步成功后：test_camera_quality.tcl→三branch验证（validator新status ACTUAL_HOST_PHOTO_ENHANCEMENT_EXACT、source_kind host_photo，不冒充camera）；snapshot live→validate；measure cadence10s→封存新保护快版与报告。已有protected成功版可恢复（不过USB硬件坏仍需人处理）。旧cached_verified包完整，r4dstatic_verified也保留。

## 2026-10-26 11:32 当前：正常光保护已通过照片回归，v5已上板，正在三分支实板测试

用户已接受缓存版延迟，要求继续画质；随后说“不方便布置，先用已有照片测试”，因此没有要求用户改灯/拍照。摄像头保持可用，当前已升级到 **E:/FPGA_Enhance_Work/multinex_camera_protected_20261026/**（同bit/PS/BSP，独立新ARM，581224B），SD未写。

照片测试：**camera_quality_20261026** 冻结匹配实时几何/量化：同中心裁剪800x480、RGB565零扩展、2x2平均400x240，GT同裁剪平均但不加565量化。原our485验证12对只用于规则选择，已有LOL-v2 20对仅作回归（此前已看过，normalGT仅10个独立SHA，不是全新盲测）；纯Mult暗光PSNR18.57046/SSIM0.82758，旧NN8 18.59689/0.68226，Gamma16.89693/0.69411，原图10.16819/0.24441。正常光纯Mult严重过亮（SSIM0.79724、对原图MAE68.56），需保护。

最初mean规则网格normal阈值最低64未通过val；文件留存，簿记normal键冲突bug已修且--resume要求协议字节语义相同。第二 **camera_quality_p95_20261026** p95阈值96/112验证分离完美但回归破坏4幅背光暗图，暗PSNR17.34/SSIM0.80588，拒收未下载。第三 **camera_quality_mean_20261026** 仍只在原12验证选择，扩展globalMean网格按最大验证间隔得到**meanY32全增强/48完全保持，中间线性混合alpha256**。已有20对回归通过预先规则：暗PSNR18.73081/SSIM0.82927（19全增强，low00729 mean34 alpha224混合）；正常20均alpha0，Input保持完全相同，SSIM0.99096（565相对GT有损），不再过亮。权重未改，是ARM独立输出保护规则；不要称新训练或全新盲测/普遍画质胜出。

v5 ARM main source已加NORMAL_PROTECTION宏，prepare_multinex_camera.py protected生成独立目录；邮箱magic仍0x4D584334，version5，新增M_LUMA34/M_ALPHA35/M_FINAL36/M_SOURCE37，保护输出DDR0x04C00000；原OUTPUT0x042仍保存纯PL网络结果。即使alpha0也执行PL用于核对，画面右标题KEEP（0）/ENH（256）/MIX（中间）。DMA/cache所有权仍缓存版，保护后FINAL flush，真实LCD右侧读FINAL，左RAW。

增加host照片注入CMD2：先CMD1暂停完整帧，dow-data INPUT，再CMD2，ARM invalidate INPUT后跳过camera snapshot→同一PL核→保护→显示→自动CMD1暂停；M_SOURCE1表示host photo；CMD0恢复live source0。测试脚本test_camera_quality.tcl当前session83035，输出board_quality.log/board_quality/*，三张既有照片alpha256、0、224分支，随后自动恢复live。必须validate_multinex_camera.py逐项核对纯网络、保护数学、LCD，再实际live快照并measure cadence，封存新包。尚未核对前不可声称v5实板正确。

validator兼容v4/v5：snapshot工具新增quality.txt/protected32.bin，v5独立计算mean/alpha和FINAL；host_photo跳过已过时capture源缓冲检查，live仍核对capture2x2。profile29..33不变。新版start日志已确认v5运行>=5帧，cameraID5640 LCD7084。

## 2026-10-26 11:15 当前：缓存摄像头实测9.31Hz已封存，用户接受延迟，转向画质验证

当前板上 **multinex_camera_cached_20261026** live运行；SD未写，摄像头800x480→2x2平均400x240→同r4d PL增强→同帧左右显示。CPU缓存管理版本数值已验证：两个真实帧共192000像素均与冻结独立C++逐字节相同，capture原缓冲2x2平均/input/LCD左右图都精确，暂停后自动恢复；DMA0错误。10.308秒96次实际增强显示更新，**9.313154831Hz**。单次核心约78.7~78.8ms，snapshot13~15ms/render6~8ms，循环100~101ms（连续统计含偶发134ms）。用户先反馈未缓存版218ms延迟高，已优化并上板，用户现明确“明显改善，先继续画质验证”。不要继续压分辨率或换模型抢速度，下一步改为画质。

恢复包 **E:/FPGA_Enhance_Work/multinex_camera_cached_verified_20261026.zip**，SHA **aea04a7a17548aaa23473e2d2249ead3bad401b2807822f291c7807e340eb83a**，CRC通过；入口摄像头与延迟优化结果.md、board_deployed.json、snapshot_01/02验证记录。源码multinex_camera_main.c默认USE_DDR_CACHE0，prepare_multinex_camera.py cached会建缓存版目录和编译-DUSE_DDR_CACHE1。已有ELF禁止覆盖，后续改新候选目录。

已通过async请用户固定摄像头，对准带文字的书或包装盒并保留明暗区域，先开正常室内照明，准备好后采集正常光基准，然后请求同一场景调暗。问题选项“正常光场景已准备好 / 现在不方便布置，先用已有照片测试”，尚待回复。继续独立准备质量采集/指标与冻结协议，不要此时停着等“继续”。当前预览正常光增强侧偏亮且有高光溢出，不可称所有画质都好。无GT摄像头不能算有意义的PSNR/SSIM或把亮度/梯度当画质提高；先比较过曝、暗部、噪声、文字细节，后续正常光保护需与原纯网络输出分开记录。识别尚未启用，先做好质量再同权重评价收益。

## 2026-10-26 11:08 摄像头已接通；用户反馈延迟，缓存版已再次上板且逐字节通过

用户视觉确认“颜色正常，但是延迟太高了，之前的延迟没这么高”，将当前重点转向低延迟。第一camera版实板snapshot_01完整PL输出96k像素/同帧LCD均精确，Dcache全关，循环0.21849秒约4.58Hz、核心0.07878秒；目录multinex_camera_20261026保留可恢复。

新缓存版 **E:/FPGA_Enhance_Work/multinex_camera_cached_20261026/** 已编译577484B、下载启动，仍同SHA r4d bit/PS/BSP/400x240输入；只改ARM缓存管理，无分辨率或数学近似变化。MAIL所在1MB设NORM_NONCACHE后启用Dcache；完整旧采集帧invalidate→2x2采样，input flush到PL，output invalidate，LCD frame flush后parking。保留park0/1完整帧所有权切换，未采用更冒险的循环竞态取帧。

缓存版snapshot_01真正回读与独立冻结C++参考全96k RGB像素精确；另外完整capture.bgr24的2x2 RGB均值与input精确，LCD左右两幅也与对应input/output精确，DMA错误0。profile给kernel0.078714640s、snapshot0.014703465s、render0.006091608s，整个循环0.100704876s约9.93Hz（只是该循环样本，需连续计数验证）。sensorID0x5640、LCD0x7084，默认摄像头自动曝光。实际DDR预览看到正常光右侧过亮/高光，不能称所有画质变好或识别提升。

正在measure_multinex_camera.tcl，对缓存版运行10秒计数和错误检查，输出live_cadence.csv/log；后续还要第二次snapshot数值核对、封存缓存版恢复包/报告。当前板上缓存版正在live更新，SD未改。此后优先真实暗光/正常光质量和延迟优化，识别另评，不能把旧NN8流式即时性与全帧SE模型混称同等延迟。

## 2026-10-26 下一步摄像头接入：新ARM已编译，正在启动

用户问“下面做什么”，结合此前持续自主推进授权，正在接回摄像头，不写SD。目录E:/FPGA_Enhance_Work/multinex_camera_20261026，复用已验证r4d **同SHA bit/XSA/PS init/BSP**，只改独立ARM程序。已有采集硬件完整，不需重做Vivado。摄像头800x480→ARM 2x2 RGB平均→400x240整数增强→800x480屏幕两幅400x240，保持5:3比例，标签RAW/ENH。左右使用同一输入帧，非不同时间的直通/增强混拼。

源码starter/downstream/multinex_camera_main.c，prepare_multinex_camera.py调用ARM gcc O2（主程序-Wextra-Werror），已完成编译camera.elf574040字节，LOAD[0x100000,1156368]，无DDR别名；保留已验证静态版本和zip不改。采集新独立DDR0x06000000三帧，S2MM写park0/1轮换，等writer current帧切到next后1ms排空，再2x2取old完整帧；不启动循环保管写冲突。LCD0x02000000双显示park，input0x04000000/output0x04200000/scratch0x04400000/diag0x04B00000。Dcache禁用。Mailbox magic0x4D584334版本4，command1暂停增强帧完成后ACK，command0恢复；snapshot tcl抓取真实input/output/scratch/diag/LCD图，Python独立C++参考逐字节核对，并验证LCD两半与同一帧RGB一致。

正在start_multinex_camera.tcl，日志新目录jtag_start.log（工具返回session另看），必须成功>=5增强帧再snapshot_multinex_camera.tcl 新目录，然后validate_multinex_camera.py 新目录。尚未验证前不能称摄像头已成功/帧率已测。无识别核、摄像头默认自动曝光，量化RGB565展开到888。若失败要定位；必要可用静态start脚本恢复r4d。不可覆盖旧静态板卡结果或把旧全帧0.308秒当新摄像头FPS。

## 2026-10-26 10:51 最终：r4d已下载并实板通过，整帧加速11.93倍

最新用户“可以上板了”恢复授权后，已经完成全部JTAG下载、ARM启动、十项实板输入回读、逐字节验证、真实图最终显示和恢复包封存。当前开发板运行r4d，左RAW右ENH静态真实暗室照片，摄像头采集和识别均未启用，SD未写。下文所有暂停/未下载记录均为历史。

工作根 **E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/**：board_full/readback_validation.json为ACTUAL_BOARD_NUMERICAL_PASS，十项628231像素全输出精确且与r3b相同，控制诊断/保留特征精确，输入FNV均正确，VDMA错误0。400×600实际0.193273932秒（旧2.295208619秒）；480×800实际**0.307791150秒**（旧3.671899163秒），**11.92984倍**。最后display_final再次08_full精确，0.307925223秒，保留真实照片显示。计时为ARM启动IP到done，排除主机传图/显示合成，不能称摄像头端到端FPS、画质提升或识别率提升。

board_deployed.json与handoff_status.json状态DEPLOYED_FASTER_STATIC_IMAGE_BOARD_VERIFIED，hardware_paused_by_user=false/downloaded=true。实际整机100MHz、LUT40115、FF48628、BRAM Tile71、DSP163，setup+0.369ns/hold+0.054ns/bus_skew最小8.459ns。恢复包 **E:/FPGA_Enhance_Work/multinex_fast_verified_20261026.zip**，SHA256 **6b657ddff6e12bb89ddee23ff662ec5f39df0677ecea3fae807547e383ab39b4**，CRC通过。入口README.md、加速版实板结果.md；actual_board_comparison.png来自实板DDR回读，已查看；不是LCD拍照。

原r3b完整已验证zip与旧SD/旧模型保留；此前offline candidate zip未修改。working root旧离线handoff另存offline_handoff_status.json，待上板说明已加历史标记，避免把它当当前状态。用户要求不在中间等“继续”，本轮已完整完成优化→验证→下载→实板核对；下一步若继续项目应做摄像头适配或独立识别收益评估，不能把本轮等效加速声称新训练/识别变强。不主动写SD。

## 2026-10-26 用户已恢复上板授权：正在下载r4d

最新用户明确“可以上板了”，覆盖下方暂停板卡要求。正在下载已接收离线候选multinex_fast_static_r4d_20261026，start脚本session69405，日志jtag_start.log。重新离线门控已通过、bit/ELF/PS/旧文件SHA均核对。继续自主完成JTAG启动→十项board_full→独立validate→真实图display_final→validate→finish_multinex_fast.py。不写SD；新版实际输出和速度仍待本次实板结果，不能先声称已通过。

## 2026-10-26 02:17 最终：r4d离线候选完成；用户关电暂停，未下载新版

**最新用户关电暂停约束仍有效，禁止自动连接/扫描/复位/下载，等用户回来明确上电后再进行。** 用户允许继续电脑端优化，现已完成该部分，不再留后台编译任务。

新版 **E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/**：9例C/627908像素精确，4例真正RTL/1860像素和48诊断/7440scratch精确，IP封装核验通过，实际Vivado整机布线/bit/XSA生成、独立物理审核和离线门控全部通过。整机实际LUT40115/53200、FF48628/106400、BRAM Tile71/140、DSP163/220；100MHz，WNS+0.369ns、WHS+0.054ns，总线偏斜均满足（具体最小余量见handoff_status.json）。PS init和driver控制头逐字节等于基线，复用同SHA已编译ARM ELF。仍保留既有外部IO约束不全等限制。

入口 **待上板说明.md**、handoff_status.json状态OFFLINE_CANDIDATE_READY_HARDWARE_PAUSED_BY_USER、offline_acceptance.json。候选包 **E:/FPGA_Enhance_Work/multinex_fast_r4d_offline_candidate_20261026.zip**，SHA256 **72e4072a3b1e8dcb20dbb887879d66878c8d5cdc020f4656f0d60a00533a838b**，CRC通过。此包不是实板验证发布包；没有新板卡数值/速度，未接JTAG、未下载、未写SD。r3b旧基线/旧模型/旧SD文件SHA保留。不要把旧3.671899秒作为新版速度。

用户回来确认上电后剩余：start_multinex_static.tcl（易失JTAG）→run_multinex_static.tcl board_full（10项）→validate_multinex_readback.py→display_final 08_full→再validate→finish_multinex_fast.py（必须大图更快且输出全相同才封存verified包）。此时不能运行finish，因为board_full不存在。不要继续训练此前已拒收的识别候选，当前是等效增强硬件速度优化，不能宣称识别率提升或实时摄像头。SD保持不写。

## 2026-10-26 02:08 用户暂停板卡：允许继续电脑端，禁止连接/下载

最新用户明确：“先暂停吧，我要睡觉了……你可以继续优化模型，但我要关闭单片机电源了。”已回复可关电、工程/旧版文件保留、SD未改。**立即暂停所有JTAG连接/读取/复位/下载，不再运行readiness或start/run脚本；等用户回来明确重新上电后再实板验证。** 可继续现有电脑端HLS/Vivado优化、仿真、编译和离线门控。这条覆盖下文此前“JTAG在线可直接下载”的授权与状态；不要因为编译通过而自动连接。

当前r4d整机build仍在session71057、目录multinex_fast_static_r4d_20261026；增强核综合已完成LUT34592/FF36930/BRAM Tile61/DSP163，尚待最终PNR。允许继续build→accept_board→audit→offline acceptance，生成待上板说明与candidate包；**不能执行start/run或finish_multinex_fast.py，因为新实板结果尚不存在**。用户关电后r3b易失运行停止；旧验证zip与SD文件均完整。

## 2026-10-26 02:03：r4d数值/IP通过，第二轮整机正在编译

此段覆盖下方状态。r4d九项C测试627908像素全精确；四项RTL1860像素、48诊断、7440scratch整数全部精确（工具与独立dump审计）。mul_q16综合确认4周期延迟/II1、估算5.788ns，替换r4c实际失败的一周期长路径。HLS总资源BRAM18=140、DSP105、FF51789、LUT57253。已完成local revision1 IP封装，completion.json核验参数原SHA和ZIP/声明文件；未改变参考模型。

第二轮板级工程 **E:/FPGA_Enhance_Work/multinex_fast_static_r4d_20261026/**，active exec session **71057**，build.log；使用新HLS r4d。正在Vivado batch，下一步仍为accept_board→audit_physical→accept_multinex_static.py→start JTAG→10项board_full→validate→display_final 08_full→validate→finish_multinex_fast.py。旧r4c整机时序失败，不可下载；板上仍r3b。当前JTAG在线，前次只读检测mailbox版本3、state3、两ARM running，供电无需重复询问。不得此处结束让用户再喊继续，不操作SD。finish_multinex_fast.py已准备，要求实际输出与基线全相同且两大图都更快，才能封存新恢复包。

## 2026-10-26 01:57：r4c整网数值通过但实际布线时序失败，r4d正在修复

r4c实际整机已生成bit但**未接收、未下载**：WNS=-0.936ns，WHS=0.014ns，44个setup失败端点。关键路径是back/mul_q16产品寄存器（控制→DSP/carry链），因此不靠降标准接收。候选位于`multinex_fast_static_20261026`，保留失败证据。板上仍是r3b。

新`multinex_hls_r4d_20261026`采用同一r4c参考数学，将mul_q16 signed34×34全68位乘积显式BIND_OP DSP latency=3、函数PIPELINE II1，再按原规则round16；已证明实际乘积<signed59故转int64无截断损失。生成脚本prepare_multinex_fast_d.py。HLS build正在运行，需重过9C/4RTL再导出。board helper已改指向**multinex_fast_static_r4d_20261026**，finish_multinex_fast.py也指向此目录，尚未构建/部署d。用户要求自主一直做到实板验证，不得此时结束等继续。不写SD。

## 2026-10-26 01:40 最新：r4c整网C/RTL精确，开始独立整机编译

此段优先于下方旧“正在排查”记录。r4/r4b失败原因之一已实证定位：HLS2020.2把正数32768×65536融合为有符号32位MAC加数，在纯白Cb先验产生-65536错误。r4c使用非内联流水signed18×18→36乘法函数隔开错误融合；全部展开的空间卷积使用分组部分和，取消volatile累加器。参考权重/舍入/期望结果未改。

`multinex_fast_probe_c_20261026`64先验/Dense向量真正RTL全通过。`multinex_hls_r4c_20261026`9例627908像素C测试和综合通过；4例tiny/odd/black/white真正RTL 1860像素、48诊断、7440scratch整数全精确，独立rtl_dump_audit.json再次确认。HLS估算LUT57177、FF51534、BRAM18=140、DSP105；LUT超过设备，仍需实际Vivado fit/timing，禁止声称已放下。新IP名multinex_fast，外部ABI不变。IP导出遇2026年core_revision溢出，仅局部脚本revision1修复，不改安装工具/RTL。

接下来自动完成export核验→`multinex_fast_static_20261026`独立整机→物理时序审核→JTAG→同10项实板回读/测速。尚未下载r4c，板上仍是通过的r3b（800x480 3.671899秒）。不写SD，不覆盖基线。用户要求全流程连续推进，不要中途结束等待“继续”。

## 2026-10-26 当前进行中：静态r3b已真实上板通过；用户要求连续优化/下载，不要中途等“继续”；正排查r4流水数值偏差

**本节优先于下面所有“未上板”状态。** 用户明确新增指令：“就是你一直完善模型然后下载到板子上什么的，就不要在一半停让我喊你继续”。应持续自主完成改进→验证→下载→实板核对，仅在必须用户供电/接线时提问；不要在中间里程碑结束等下一次“继续”。没有许可创建subagents，禁止主动delegation。SD新版本暂不写的约束仍有效。

### 已完成的整机和实板基线（需要保留）

目录 **`E:/FPGA_Enhance_Work/multinex_static_20261025/`**，已生成bit/XSA/ARM ELF，并真正通过JTAG启动。JTAG在线能识别APU/两ARM/xc7z020，不必再次询问供电确认；若后续扫描失败再请人配合。板上目前是这个静态图应用，最后成功显示/回读case08_full真实暗光照片（左RAW右ENH），无摄像头采集、无识别核、未写SD。ARM源main/app_src（Debug O0构建）、固定地址见memory_map.json。

**实板数值**：`board_full/readback_validation.json`为ACTUAL_BOARD_NUMERICAL_PASS，10项/628231像素全输出逐字节一致，全部输入FNV正确/VDMA错误0，控制图mean/gate和保留scratch也精确。含1x1/17x19/黑白随机/1x800/480x1/400x600真实照片/480x800 resize真实图/最后重复odd验证大图后缩小。另`display_final/`再次case08_full单独通过，确保最后屏幕有真实照片，非测试噪声。`board_deployed.json`、`verified_baseline.json`记录实际结果。400x600内核墙钟2.295208619秒，480x800 **3.671899163秒**（约0.27fps，不能称实时）。计时从ARM启动IP到完成，排除电脑JTAG传图、FNV与显示合成，含轮询量级/DDR和LCD竞争。

**实际整机PNR**：LUT30471/53200、FF36574/106400、BRAM Tile77.5/140、DSP120/220（NN120，区别于HLS预估47）。100MHz，WNS0.094ns/WHS0.006ns，bus_skew5项最差8.953ns满足。physical_audit.txt、bus_skew.rpt、clock_interaction.rpt完整；仍继承外部IO delay不全/摄像头时钟布线警告，不是完整外部接口签核。PS7 initSHA仍d474422bbe07d4e96bc84d19b8d9574bb3483004b0bf97d47f3ce6e0930802e7，原PS设置未变。

**恢复基线包**：`E:/FPGA_Enhance_Work/multinex_static_verified_20261026.zip`，SHA256 **442d66032438fe1b49fcf6a5a28921e0a900d8aa000b01d49c9be2d82e182de4**，CRC通过；入口`实板基线说明.md`。实际图像预览`actual_board_comparison.png`已查看，暗室桌椅图明显变亮，噪声也被放大；这是实际DDR回读绘制，非LCD拍照/非软件预期图。可恢复文件multinex_static.bit、multinex_static.elf、ps7_init.tcl、start_multinex_static.tcl（会看ACCEPTED_FOR_JTAG.txt）。新bit是易失JTAG，不是新SD启动镜像。

### 目前主动推进的速度优化r4（未通过，不可下载）

目录 **`E:/FPGA_Enhance_Work/multinex_hls_r4_20261026/`**，workspace生成脚本starter/nn/prepare_multinex_fast.py、multinex_dense_fast.h。以r3b为数值参考，无权重/LUT/舍入改变；Dense变成零填充3x5并行矩阵，输入/输出完整分组，sqrt改34位restoring/最终17位平方（证明RGB8平方和<2^34，sqrt<2^17）；feature_rows[7][5][800]、masked_rows[3][3][800]、back rows[3][3][800]按通道分组；front主像素II7、PW/ReLU II3、back II9，点积函数共享数量前5/后1，dense/mul函数限1，prior管线II3/共享1个除法器。所有II综合均满足，627908像素9案例Csim精确。HLS预估LUT59401超过设备53200、FF53993、BRAM18 140、DSP109；r3b实际Vivado比HLS估算显著小，因此如数值通过，可尝试实际综合，不能只按预估声称fit；需要最终PNR门控。

**r4真实RTL失败**：`cosim.log`第一tiny绿色got241/expected247；独立audit所有3案例RGB/diag/scratch都错。tiny mean/gate实际 `[57651,101504,90152,0,102708,20924,-13634,37127,27819,-49498,-8695,-10848]`，期望 `[63895,101679,88895,0,98640,15129,-12955,37337,28337,-49498,-8695,-10848]`；scratch实际 `[0,102708,20924,-20663]`、期望 `[0,98640,15129,-22697]`。status均0。候选未导出/未上板，板上成功r3b保持。已告知用户在定位而非覆盖旧版。

**正在运行隔离探针**：`E:/FPGA_Enhance_Work/multinex_fast_probe_20261026/`，生成脚本starter/nn/probe_multinex_fast.py，active exec session **66188**，build.log，64个固定向量（5控制×12dense层再补齐8批）。probe.cpp直接包含r4 priors、dense、数学helper，在batch8外层II7下分别检查5个先验+5个Dense结果，期望从冻结layer_traces.npz提取。目的是隔离“prior共享除法/并行Dense返回路由”与“空间卷积volatile累加器在完全展开+跨像素流水中被重用”的问题。若探针通过，下一步优先把r4 fully-unroll dx/c中的volatile acc改为原生int64部分和数组/平衡加法（无可变volatile寄存器），再做完整RTL。若探针失败，按vector/column查vectors.json确定prior还是Dense先失败。不要只改预期值，不得下载失败模型。

后续速度候选工具已准备`starter/downstream/prepare_multinex_fast_board.py`，模式export→revision1→verify_hls→prepare_board→accept_board，目标预设`multinex_fast_static_20261026/`、IP `fpga.user:hls:multinex_fast:1.0`。**必须先修好r4 RTL才调用export**。准备fast新工程时导入原NN8 bd去旧NN/bridge，4 M_AXI共享HP0、control43c20000、直连VDMA24bit显示。外部ABI不改可复用已实板通过的ARM ELF（脚本校验新XSA/PS init/硬件头完全相同），不是冒称重新编译。HLS模块路径若改r4b要同步脚本HLS常量。真实PNR合格后再JTAG和同10案例回读/计时，只有精确且更快才选新版；否则保留r3b并继续定位/调整并行度。

### 本轮已有工具注意事项

work rootASCII，Python E:/FPGA_Enhance_Work/nn_env312/Scripts/python.exe；Vivado E:/Xilinx/Vivado/2020.2/bin/vivado.bat，HLS E:/Xilinx/Vitis_HLS/2020.2/bin/vitis_hls.bat；XSCT E:/Xilinx/Vitis/2020.2/bin/xsct.bat。不要用GUI RTL分析，会因中文用户路径不稳。board构建占30分钟，只有在有新改动/失败时重跑。ARM build_app.tcl已成功；XSA Windows修复仅Makefile TAB #echo→@echo，未改安装目录，ps_init一致。audit Tcl第一次用了不支持的redirect导致报告命令失败，已删除重复check_timing（timing_summary中已包含），重新audit成功。所有旧位流/SD文件仍核对SHA未变。

板上内存：frame3×1152000B@02000000，mail03000000，input04000000，output04200000，scratch04400000（int32[4N]），diag04b00000（12int64）。app限定1MB..16MB链接避免重叠；D-cache关闭兼容host JTAG+PL。mail magic4d584633/version3，state2busy/3done，request index3/done4、h5/w6、ticklo7/hi8/freq9、fnv11/12、DMA13/error14/heartbeat15。run脚本支持正整数案例数或case ID。板上最后真实照片用`run_multinex_static.tcl outdir 08_full`，测试新代码后也应留下真实图，不要停在随机噪声案例。

## 2026-10-25 最新：融合r3b通过全尺寸C仿真/小图RTL，IP已封装；DDR临时区和流量大幅下降

本节优先于下方r2“下一步融合/尚未导出IP”的记录。用户“继续”后本轮完成硬件数据流优化，没有改权重、LUT、舍入或识别器，也没有连接JTAG、操作板卡或SD卡。尚未生成新整机bitstream。旧r2的全部顶层manifest文件，以及其记录的旧bit/BOOT/模型冻结ZIP/CNN权重，重新SHA校验都未变。

**接收目录 `E:/FPGA_Enhance_Work/multinex_hls_r3b_20261025/`**，入口`本轮融合优化结果.md`，`completion.json`状态 **FUSED_CSIM_SYNTH_RTL_IP_VERIFIED_NOT_INTEGRATED**。可交付包`multinex_fused_ip_bundle.zip`，517615字节，SHA256 **dbbdc0aff6c6c40053719eb49de3ee317d5fcfada17ef189e1d9839e33ae135f**，CRC通过。内有ip/（Vivado IP目录）、sources/、licenses/、verification/，并非bitstream/SD启动文件。

新源码`starter/nn/multinex_fused_hls.cpp`，准备/核验/交付脚本为prepare_multinex_fused.py、audit_multinex_fused.py、finish_multinex_fused.py、prepare_multinex_fused_export.py、verify_multinex_fused_export.py。prepare复用旧prepare生成冻结参数/测试，然后覆盖为融合实现，当前DEST为r3b；有completion.json会拒绝覆盖，后续新版本必须换目录。数学helper multinex_math.h从已冻结r2抽取，hls_parameters.h与r2字节相同。

架构：每branch前半段RGB先验→stem/7x7 attention/projection/sigmoid/mask→3x3 DW/PW/ReLU全部在7行特征+3行masked-stem缓存中完成，只把3通道ReLU写DDR并同时累加全帧和；用本帧SE gate，后半段3行ReLU缓存→depth/MSEF/head。illum先完成并存luma，chroma复用同一ReLU DDR区域，直接融合RGB输出。边界特征和masked-stem必须真补0，不能在图像外运行黑色输入先验/网络（否则EPS/偏置导致不等价）。feature/masked缓存signed18，后半ReLU缓存signed25；MSEF的signed33值留在native64/ap34寄存器，不截到int32。

**接口已变化**：input/output仍uint32 RGB888低到高R/G/B/0；scratch现在是`int32[4*h*w]`，前3N最后保留chroma ReLU，后N保留luma head；diagnostics仍int64[12]，status0/-1。原图、结果、scratch、diagnostics不能alias，整次任务原图必须不变。最多480高800宽。M_AXI depth1024/4096仅TB适配器分配，不限制硬件地址；不能混用旧r2 int64[24N]驱动。

800x480 scratch **6144000字节**（r2为73728000，降到1/12）；按源码逻辑的每帧DDR有效载荷 **27648096字节**（72字节/像素+96诊断，r2为702643296），降低约96.1%。这是读写次数核算，不是总线实测，未计协议/宽度转换；30fps仍需829MB/s有效载荷，且计算吞吐尚不满足证明，不能宣称实时。

**测试**：9个HLS C输入，共627908像素/1883724输出字节精确；含400x600原真实图、新增480x800由同真实图resize的数值边界测试、黑/白/随机、1x1/17x19/1x800/480x1。另60个mean/gate、10512个保留ReLU/luma整数精确，非法尺寸不写内存。真正RTL 3调用（tiny/odd/black，共1092像素）工具Pass，独立读RTL dump又核对RGB/36 mean-gate/4368保留int32/状态全部一致。完整800x480还只是C仿真，未做完整帧RTL、随机AXI背压/复位或实板。默认AXI RTL模型同3输入总1059278周期，比r2的1469930降27.9%；不能按小图外推板卡帧率。

**r3b HLS单核**：LUT39323/53200、FF38509/106400、DSP47/220、BRAM_18K178/280。10ns目标、2.7ns不确定性，估算7.300ns满足HLS预算，未布局布线。中间r3同样C/RTL和独立dump通过，但直接对全18层ROM做7路读导致复制ROM、BRAM_18K232；r3b在每branch开头加载tap到小型分组LUTRAM，降到178，不改变参数。中间目录`multinex_hls_r3_20261025/`留作资源对照，不选为接收版。

**IP**：`fpga.user:hls:multinex_fused:1.0`，目录`r3b/multinex_project/solution_100mhz/impl/ip`。常规HLS export因core_revision 2610252311超过int32失败，已仅在该目录生成run_ippack_revision1.tcl，将Revision改1并check_integrity，再用Vivado batch封装；没有改安装脚本或RTL。raw IP ZIP SHA **8f93a9b82a5132e904c766c1e25cd290d993eed11555e9c3942ad7cdb5690b83**；component SHA **3fb34aa391ea024be5189e958bb39bd396671728e9680153d86e5a097fe8c7a9**；CRC、component一致性、258个声明文件、57个Verilog文件都核对。IP包装成功不代表整机能放下/时序通过。bundle含完整版权/许可证。

**下一步先独立静态图片工程，不直接拼旧双识别链**：旧已布线工程总LUT19937、BRAM18等效148；NN8占5874 LUT、34 BRAM18；两识别器各约3.8k LUT/47 BRAM18/21DSP。减旧NN8再加r3b的混合粗估为53386 LUT/292 BRAM18，超7020；先移除两个PL识别器做增强专用静态验证，粗估45681 LUT/198 BRAM18，之后复用单识别器（粗估49523 LUT/245 BRAM18）或ARM做同权重识别。粗估混合旧布局与新HLS，尚不计新AXI互连/物理优化，不保证放得下。新板卡工程需独立目录，连接4个M_AXI到PS DDR、control到AXI-Lite，修改ARM缓冲格式、cache维护和display数据路径；先回读精确性/测整帧耗时，再摄像头。旧屏幕/JTAG/SD恢复包保持不变。

## 2026-10-25 最新：Multinex HLS r2的C仿真/综合/Verilog RTL联合仿真通过，尚未集成或上板

本节优先于下方早先“尚未做HLS”的记录。用户继续要求先完善模型再摄像头；本轮没有连接JTAG、下载板卡或操作SD卡。

接收的计算核目录 **`E:/FPGA_Enhance_Work/multinex_hls_r2_20261025/`**，入口 **`本轮HLS结果与下一步.md`**，`completion.json`状态为 **CSIM_SYNTH_RTL_COSIM_VERIFIED_NOT_INTEGRATED**。冻结整数/浮点模型和旧识别器均未改，原候选ZIP和旧bit/BOOT/CNN SHA核对未变。新增实现不是新训练，不宣称识别率提高。

源码在starter/nn/multinex_hls.cpp、multinex_hls.h、tb_multinex_hls.cpp、prepare_multinex_hls.py、audit_multinex_rtl_dump.py、finish_multinex_hls.py。prepare默认输出r2 ASCII目录；有completion.json会拒绝覆盖，应为下一版改新DEST。冻结参考仍为multinex_fixed_w18_20261025及其candidate.zip。HLS2020.2，目标xc7z020clg400-2，10ns/2.7ns uncertainty。

8个C仿真输入、243908像素、731724输出字节与冻结整数参考一致：黑白随机、1x1、17x19、400x600真实图、1x800、480x1；5控制的60个均值/gate值也一致。无效尺寸C测试拒绝且不写内存。真正Verilog RTL联合仿真3调用（1x1、17x19、24x32，共1092像素/36均值gate）工具Pass，独立解析RTL dump又对照冻结预期，6组最终保留scratch共19656整数精确，status均0。注意这不是完整400x600/800x480 RTL或实板验证。

HLS单核估算：LUT28637/53200，FF26560/106400，DSP36/220，BRAM_18K107/280（不要与140个36Kb tile混用）。估算时钟7.300ns满足该HLS有效预算7.30ns，没有整机布局布线。动态尺寸整体latency=undef；3小图RTL默认AXI模型总1469930周期，不能外推实板FPS。

结构为共享7空间tap计算器+逐通道点卷积+整帧多遍DDR。r2按行burst预取/写回、1x1输入行缓存、空间dot加流水。输入输出uint32 RGB888（低到高R/G/B/0），scratch为24*h*w个signed64；800x480 scratch为73728000字节（70.3MiB），另输入输出各1536000字节。最多480高、800宽；diagnostics12个signed64；status0成功/-1尺寸错；缓冲区不能alias，后续ARM负责DDR/cache一致性。M_AXI depth1024/24576只是RTL TB适配器分配大小，不截硬件地址；当前RTL测试不超过1024像素。

**仍不适合实时摄像头替换：**按源码逻辑DDR payload，800x480一帧约702643296字节，30fps超过21GB/s（不是实测总线带宽，未计协议开销）。主因全部中间算子落DDR且7/3行反复读取。下一步应做滚动行缓存和算子融合，把整帧DDR依赖收敛到SE所需的6通道ReLU特征/原图，而非直接拼接现有显示直通链路；之后补全尺寸/复位/背压测试、独立静态图片工程集成与板上数值回读/测速，最后摄像头。

首版目录`multinex_hls_20261025/`保留作失败证据：其RTL计算的RGB/mean/gate/19656中间值都精确，但status开头写临时-1导致ap_vld输出提前被捕获，工具Cosim FAIL，不能用r1。r2 status改成每调用只写一次最终值；r2首次综合另因强制函数共享引发AXI/ap_auto模式冲突，日志attempt1_csim_pass_allocation_error.log保留，已删除多余ALLOCATION限制并重新完整Csim/synth/cosim通过。最终build.log/cosim.log为依据。原先宏作depth在2020.2解析失败已改字面常量。所有当前进程已结束，没有后台训练或仿真。

未完成：封装IP导出（2026年revision溢出须局部修复）、整机Vivado综合/布局布线、完整尺寸RTL、随机背压/复位、实板/摄像头/SD。保留原识别器，不要采用此前未通过的新训练CNN。先前量化/画质/识别成绩看下方，HLS算术等价不会自动让识别器变强。

## 2026-10-25 继续轮次最终：Multinex整数/C++通过；识别保持候选未满足替换标准

**最终结果覆盖本节下方运行中记录：**session48503已完整897输入/5382预测结束，test_complete.json完成，无后续调权重或阈值。新198正常：旧CNN raw162/NN8106/Multi152，新CNN raw159/NN8138/Multi155；同198人工1/8：旧raw130/NN8153/Multi160，新raw147/NN8153/Multi160；501自然暗回归：旧raw447/NN8409/Multi422，新raw449/NN8408/Multi425。新识别器独立接收规则及严格增强收益规则均未通过，不能直接替换。人工暗原图识别改善130→147属于识别器训练收益，不是增强收益；正常162→159仍退步。保留所有5382条实算结果。原始NumPy慢测试已主动中断，最终唯一完整批次用已逐位验证的C++整数增强，未改变舍入/模型/测试选择。

交付入口 **`E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025/本轮模型完善结果.md`**；同根`handoff_status.json`为INTEGER_ENHANCER_VERIFIED_HOST_CPP_RECOGNIZER_TEST_COMPLETE_NOT_DEPLOYED。候选ZIP **`E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025_candidate.zip`**，11,264,831字节，SHA256 **a52b86eb532d013e668d5f9efbb1de43406280cea98d292b6dbd9f8ff9407594**，CRC通过。本地553文件有handoff_manifest.json；ZIP省略完整中间PNG/原图/逐层原始trace，保留测试向量NPZ、所有逐项CSV、模型/源码/许可证/4张全部20对总览。四张预览已经查看。复制官方浮点基准至upstream_reference，新CNN至recognizer_candidate，HLS位宽/同帧调度合同在HLS移植约定.md。当前成果是整数CPU模型和独立C++，尚未做新HLS综合/RTL/新位流，物理板卡和SD未改；旧增强/识别器/成功位流/旧BOOT文件SHA再次核对未变。

下一步应以已冻结整数/C++结果为基准实现真正可综合的HLS（不能直接综合带vector/文件IO的host参考），比较同帧两遍处理和重算的DDR/计算取舍，保持原有识别器和恢复包。识别仍需真实低光有真值数据及避免损害清楚数字的策略；不要将此候选包装成全面更强的识别模型。

本节优先于下方旧轮次。仍未连接JTAG或改板卡/SD。用户要求先完善模型再摄像头，不自动下载。新增强参考根`E:/FPGA_Enhance_Work/multinex_fixed_w18_20261025/`，失败的首轮16位权重/最近LUT在`multinex_fixed_20261025/`保留，不要误用。

已完成所有算子的整数CPU参考，包括RGB先验、除法、integer Newton sqrt、LUT插值、7x7/3x3/pointwise、同帧SE均值、原始MSEF的depth(x)*(x*gate)+x、融合。AF16，权重signed18逐层WF，最高折叠系数82.16；bias/acc参考int64。4097项[-8,8]步1/256的sigmoid/tanh整数插值。conservative_bounds证明所有RGB8、最多800x480像素范围；MSEF illum输出保守33位、最终43位，最大直接乘积59位，64位足够；不能全截int16/int32。

12张原TRAIN验证照片+黑白随机/1x1/奇数尺寸共17输入：最大单图MAE0.2483，平均caseMAE0.06053，最大单像素误差2。第一轮16位权重/无插值黑图MAE1.21拒收；所有精度修改仅据验证，不用新测试。`validation_complete.json`为VALIDATED_INTEGER_REFERENCE_NOT_RTL_OR_BOARD。

独立标量C++由Vivado2020.2自带MinGW编译静态exe；5控制逐层239248值全部精确，另400x600真实图整输出字节一致，总242628像素。`cpp_reference/verification_complete.json`为INDEPENDENT_CPP_NUMPY_INTEGER_EXACT；exeSHA2eb7289db70c9f5f305cc2b0c84187653b312c03409247db82ecc005aded622d。**这是hostC++，不是HLS Csim/RTL或实板通过。**

新增固定镜像LOL-v2-real文件排序[20:40]的20对（之前只看过[:20]），RGB565/RGB888两格式，输入格式内公平比较，不据结果调权重/位宽。RGB565：旧NN8 PSNR17.79086 SSIM.55873，Multinexfloat18.63647/.77047、整数18.63701/.77048；RGB888：旧NN819.03811/.69382，Multifloat18.08125/.82330、整数18.08199/.82330，PSNR存在取舍。40输入整数对浮点平均caseMAE.04609，最差caseMAE.06290，最大单像素3。重复场景/公开预训练污染仍未独立排除，不是完全无污染盲测。数据和全输出在new_quality_test。

识别保持训练根`E:/FPGA_Enhance_Work/robust_digit_20261025/`：冻结4253TRAIN数字（400/class+额外自然暗TRAIN）和523validation（每类存储索引100:150+自然暗），生成6视图（raw/NN8/Multi各正常和人工1/8），全部是TRAIN；缓存422.64秒。第一轮12epoch每轮正常验证都比初始444/523少至少1，因严格规则选epoch0，权重数值与初始完全同，training_rejection.json已记录，不能拿不同torch存档SHA假称训练提升。

后续只据验证失败加原始65257rawTRAIN和冻结teacher KL保持、LR4e-5训练10epoch，复用缓存，不重下/重算。独立`preserved_candidate/`最佳epoch9，权重SHA **0f245995f33ac17d45fc5b8995462830d7af6cdafe4b5ffe034e1040f9446a90**，数值确实改变；正常validation446/523未退步，natural validation29例仍有限。浮点/整数预测一致率约98.1%~100%，不是无损量化；测试必须用整数结果。

最终测试按预先固定同一原始CNN/新CNN对raw/NN8整数/Multinex整数6路。新的正常和人工1/8各198张（每类TEST索引70:90后排除2自然回归重叠），另501此前看过自然暗图明确回归，共897输入/5382预测。最初NumPy增强后端较慢，已停止该任务所属原wrapper/child进程36712/37712（仅partial进度，无完成CSV）；现单独用已逐位验证的C++整数exe加速，session48503运行中。相同权重、舍入、测试选择；日志在preserved_candidate/integer_cpp_work/backend.json。旧session42521为主动中断，不是数字失败。**等test_complete.json再做最终接收/拒收，不猜结果。**

后续先等测试、按预先规则报告识别器收益和“增强相对新识别器原图的增益”，两者不可混称。未测试前不要生成候选位流。源码在starter/nn/fixed_multinex.py、validate_fixed_multinex.py、verify_multinex_cpp.py、multinex_integer_reference.cpp、test_fixed_multinex_quality.py、train_robust_digit.py、test_robust_digit.py。HLS接口/同帧调度/带宽计划见MULTINEX_PORT_CONTRACT.md。下一步完成独立交付包、预览QA、更新本节最终状态。

## 2026-10-25 最新：离线完善轮次完成，发现自然暗图退步，候选未部署

用户要求先完善模型、确认画质和已有方法不能识别的内容是否有真实收益，再用摄像头。本轮全程离线，没有连接JTAG、操作板卡或写SD；当前物理板上版本仍是此前用户确认固定门牌5/RAW5/ENH5的score64自适应固定图版本。**此前66张实板数值通过仍有效，但不能因此声称真实暗图识别普遍受益。**

本轮目录`E:/FPGA_Enhance_Work/enhancement_study_20261025/`，入口`本轮结论与下一步.md`。新增LOL-v2-real固定镜像前20对低光/正常光（40文件14,236,001字节），含相同场景多图，不是20独立场景；另有已看过LOL-v1 eval15回归。全部方法同RGB565输入：当前NN8 PSNR12.83649/SSIM0.296626，验证调参Gamma13.85/约0.38，新220参数13.81702/0.293804，公开Multinex-Nano18.19332/0.634203。不能把此PC指标当板上RGB回读或论文同条件成绩。公开预训练数据重合未独立排除。

完成161参数1800步、220参数4000步训练，96对TRAIN/12验证选择，未据新测试选轮次。220增加59参数RGB均值MLP，最佳3200步；定点参考验证平均RGB8误差<1，未做RTL。另固定SVHN每类索引10:30的200正常+200人工乘1/8测试，现版正常164/200、合成暗162/200；220旁路版164/158，不全面更好，拒绝替换。全部5600条预测保留。

**关键失败：**额外原本偏暗、未经人工压暗的100照片，RAW93、现版均值门控79、220候选83。后续假设加P95亮部保护，只用TRAIN验证1529输入（含自然暗29）选mean<=36且P95<=72；冻结另401自然暗及新200正常/200合成暗测试。401自然暗RAW354、旧均值门控330、新保护338、同保护Gamma0.5为353；仍退步，guard_v2也拒绝通用部署，不继续据此调阈值。新200合成暗RAW138、NN8161、Gamma0.5159；正常200均165。旧100自然暗回归保护84仍不如RAW93。全部4505条后续预测保留，旧100标回归，新401与新200组不重叠。低像素亮度不能证明夜间拍摄/lux。原始guardCSV的enhancement_enabled表示新保护条件，不是所有对照方法的实际使能，rejection.json有说明。

输入精度诊断（同20对、同权重，PC探索）：当前NN8由RGB565的12.84/0.2966变为RGB88815.57/0.4712；Multinex由18.19/0.6342变为20.31/0.7485。说明当前零填充RGB565低位丢失影响明显，不能归因训练提升，也未实现摄像头RGB888。

较强画质参考Multinex实际696参数，`multinex_port_candidate/`保留官方权重/源码/许可、folded_reference.pth及float数组，2处BN折叠已对12验证图+黑白随机共15例通过，误差<1e-5，RGB8最大1；仅浮点golden，**未定点移植、未生成位流**。源码审计633卷积MAC/像素+12线性MAC/帧，4亮度/5颜色图，sqrt/除法/sigmoid/tanh/7x7及同帧全局特征均值；理想100MHz@800x48030fps算术平均72.92不能当DSP/资源/帧率结论。现版NN8128DSP是替换而非叠加，不能直接拿现170/220余量断言不可做。后续需正确两遍缓存/均值策略及C/RTL数值验收，不能偷偷拿上一帧均值当原模型。

`round_status.json`为OFFLINE_ROUND_COMPLETE_NEW_MODELS_NOT_ACCEPTED_FOR_BOARD。结果ZIP `enhancement_study_20261025_results.zip` 8,851,906字节，SHA256 **50aa391de9f5d3e8d8cfc1787d5be3854d12d891d218ab3be06a54fea1a90626**，CRC通过；它是结果/候选包，省略全分辨率中间PNG及数据，不是可直接上板恢复包。完整本地1893文件有round_file_manifest.json。20对四张总览和本轮关键对照已查看，全部失败保留。当前模型/识别器/成功位流/旧SD电脑BOOT哈希均未改。

下一阶段仍先完善模型。更强画质参考和输入精度已有证据，但当前还不能声称全面优于现成模型或真实暗图识别已解决；需要更多有真值真实低光数字样本、任务保持与鲁棒策略，再定点/HLS，最后摄像头。不要把两次重训或亮部保护当作成功升级直接下载。

## 2026-10-25 用户最新方向：先完善模型，暂不接回摄像头

用户希望先确认增强能否使已有方法失败的内容被正确识别、是否提升清晰度与实际价值，再进行摄像头验证。因此下节“下一步接回摄像头”暂缓，不自动切换板上模式。本轮只审计已有结果，未训练/改权重/操作板卡。66图实板中30张合成暗图：原图19、自适应26，救回7张、原对变错0张。冻结CNN的100图电脑诊断中合成暗图RAW65、固定Gamma75、NN8 85；NN8正确而Gamma错误10张，反向0张。这100图不是全部上板，不是新盲测，也不是其他成熟神经网络基线。正常图无条件NN8反而84→61，旁路只是避免这批正常图退步。此次主要重训的是识别器，NN8权重没改，不能称已训练出全新更优增强模型。下一阶段应固定识别器、采用未参与调参的新测试集，对比简单提亮和适合场景的公开增强方法，分别评估真实暗光识别和图像质量，再决定增强网络训练/压缩；不能以提亮、放大、识别提升替代清晰度证明。

## 2026-10-25 最终状态：自适应增强CNN固定图片实板验证通过

本节优先于下方所有历史“待测/复测中/拒收”记录。当前板上为score64新位流和自适应固定图片ARM程序，摄像头DMA关闭，SD未写。最后重新启动后载入`commons_1_roi`，板上RAW=5、ENH=5、输入FNV通过；用户已确认“固定门牌5，RAW和ENH都是5”。正常亮度门控旁路，左右亮度接近。最后展示记录在`real_cnn_adaptive_image_test_20261025/final_real5_after_restart/`。

已完成无条件增强和自适应增强两轮同一批66张实板测试：每轮132路类别和margin均与独立软件整数参考精确一致，0数值不一致，全部输入FNV/SHA通过、DMA错误0，首张1152000字节DDR读回逐字节相同。注意数值一致率不等于识别准确率。正常33张原图27/33，无条件增强18/33，自动旁路27/33；同30张SVHN人工RGB乘1/8后，原图19/30、自适应增强26/30。完整门牌照片的手动ROI仅1/3正确，两张旧黑底白字8也均失败，保留全部结果。暗图是合成亮度，不是真实夜景或lux测量；识别仍限给定ROI的单数字，不是全场景定位或车牌OCR。

最终HLS C/RTL 6帧1586329像素、原生流RTL随机背压/重启/复位5帧123339像素、实际综合网表完整核2帧61593像素、实际综合分类层3组隐藏向量均通过。100MHz布线WNS0.373ns、WHS0.021ns；LUT19937、FF24403、BRAM Tile74、DSP170。原厂外部IO时序限制仍保留。CNN权重、增强权重未因数值修正而改变。门控阈值36仅用TRAIN中既存验证集校准，没有用TEST或门牌图拟合。

成功交付目录：**`E:/FPGA_Enhance_Work/real_cnn_adaptive_verified_20261025/`**；同名ZIP **8528756字节**，SHA256 **bed624a1edbfbaf2de619780026caddca89ec93075cd9ee412200cb7104213ae**。315文件及ZIP逐项哈希/CRC核对通过。入口`新版使用与实测结果.md`，另有`hardware_test_status.json`、`逐图实板结果.csv`、`全部照片与实板识别结果.png`及完整证据。预览RGB是电脑参考，标签是实板测量，不是FPGA增强RGB回读。冻结包后不改其内容；后续展示确认记录存独立运行目录。

下一步才是将当前CNN及亮度门控接回摄像头并采集实拍正常/弱光图，验证曝光变化、稳定性及识别泛化。当前不要宣称摄像头准确率。JTAG新版断电后不保留；旧SD电脑BOOT.BIN和旧摄像头候选bit已核对哈希未改。下方第一版实板41/66不一致及失败离线候选ZIP是历史证据，不能拿来恢复当前成功版。

## 2026-10-25 当前继续任务：第二个签名扩展错误已定位，score64版实板复测中

本节优先于下方“正在集成”旧状态。用户已按提示开机并连接下载器、保持通电；JTAG现可见APU/两ARM/XC7Z020，不要重复询问。当前板上是**score64新版固定图模式**，不是摄像头，SD一直未写。

第一轮native64局部卷积累加器修正虽通过HLS C/RTL及随机背压，整机`camera_real_cnn_20261025`（bit930a1fe...）实板66张仍41张数值不一致。`post_synth_check`实际综合网表也复现：全零输入margin期望7804859、实得5707707，相差2^21。`analyze_cnn_bias_extension.py`将**诊断模型内存副本**最后fc2负偏置按21位误零扩展，**精确解释全部66×2=132路实板类别和margin**，源模型文件没改；证据`real_cnn_image_test_20261025/bias_sign_extension_diagnostic.json`。这将问题定位至fc2负偏置有符号扩展，不能用输入损坏解释。第一版硬件仍拒收，保留全部失败日志。

第二修正：`real_cnn_kernel.h`最终层score也改`volatile long long`，乘积`.to_int64()`，best/second/delta原生signed64；前三层MAC同样原生volatile64，量化前界仍signed40内。**模型数学、权重和阈值不变**。独立`cnn_score_probe_20261025`只测最终分类层，通过**Vivado真实综合后**三组hidden向量，margin7804859/4798005/21625920均精确，`simulate.log`SCORE_PROBE_POST_SYNTH_PASS。

第二HLS目录 **`real_digit_training_20261025/cnn_candidate/hls_score64/`**，IP fpga.user:hls:real_digit_monitor:1.1。完整6帧1586329像素C/RTL再通过，`rtl_stream_score64`5帧123339像素AXI/backpressure/autorestart/reset/分类margin再通过。打包仍用本项目revision1脚本避免2020.2日期溢出，没改安装目录。

第二整机 **`E:/FPGA_Enhance_Work/camera_real_cnn_score64_20261025/`**，已完整布线bit生成；WNS0.373ns/WHS0.021ns（100MHz）、LUT19937、FF24403，其他资源见utilization.rpt。bit SHA **0a832187afaee8006584295dfdad89600d6d055ceb49a57836af6a19d2d91ab4**。PS7init d474422...与旧版逐字节同，XDC原厂引用同，integration_audit通过。`stage_real_cnn_runtime.py`现默认stage该score64版。

第二基线图片测试根 **`E:/FPGA_Enhance_Work/real_cnn_image_test_score64_20261025/`**，复用原固定图ELF dea2b6...，board是score64新bit/XSA。66输入=3诊断+33正常真实ROI+30同SVHN RGB×1/8。`baseline_controls`三输入包括原错色块和暗demo，类别/margin全匹配；当前`baseline_66`实板批次仍在运行（session56668）。最近52/66已完成、数值0误差；33正常真实图已完成，RAW27/33、无条件NN8 ENH18/33（这次为实板）。所有已测FNV一致、DMA0。须等待最后66/66完成再最终汇总，不要把数字识别准确率与数值一致率混为一谈。

综合网表验证score64目录post_synth_check已重启，session4788：两帧（小黑图+一个真实ROI），phase0已通过，phase1在运行。第一轮post测试曾错误把器件模型1ps单位覆盖成1ns，已标invalid并修正；后续cached DCP rename_top digit_monitor与内部同名造成递归，现顶层唯一名post_synth_core。正确测试尊重unisim原始时间单位。当前mem文件多余重复帧导致too-many-words警告不影响指定范围首帧；最终不得把未完成测试标PASS。

**新增正常亮度旁路，待实板：** `calibrate_exposure_gate.py`只用TRAIN文件既存验证索引每类前50=500，alpha1/.25共1000例拟合，不用官方test/Wikimedia。冻结阈值36（ROI整数亮度均值<=36开NN8，否则旁路），validation正常RAW411/500、无条件NN8295、门控411；.25暗RAW390、NN8398、门控402。原始CNN/增强权重没改，别称重训了增强网络。配置`cnn_candidate/exposure_gate/gate_config.json`。

自适应固定图ARM源码/ELF已编译在 **`E:/FPGA_Enhance_Work/real_cnn_adaptive_image_test_20261025/`**，`prepare_real_cnn_adaptive.py`完成`runtime_prepared.json`。新ELF先算真实输入ROI均值并决定模式，M_RESERVED16打包mean|mode<<8；主机派生脚本验证实际mean/mode、类别/margin/FNV；不发送标签或预测给板。mode0时ARM另检查RAW/ENH类别和margin全同，失败error10。CPU仅亮度统计/控制，NN8和两CNN仍PL。预期66中33门控开、33关；正常33期望RAW27/ENH27，合成暗30 RAW19/ENH26。**这些门控数值尚为电脑期望，未运行自适应实板**。

下一步：等score64基线66完成0误差及post_synth最终状态；核对首张fullDDR回读全字节；将`real_cnn_image_test_score64/board`复制到adaptive根的board，启动adaptive start_fixed_image.tcl（同一新bit、不同ELF），先3控制检查，后66批次验证。不要重训/改阈值来迎合测试。最终保存新成功包/说明、保留失败/旧摄像头包与原SD。可载入commons_1_roi真实门牌5作为最终屏幕并请用户确认固定图/RAW5/ENH5。真实大图门牌仍1/3、识别限已给定ROI单数字，暗图是合成亮度非夜景/lux。图像预览全是PC参考不是FPGA回读。最终告知JTAG临时、SD未改。

## 2026-10-25 继续任务：CNN数值修正已通过RTL，正在整机集成

用户回复“继续吧”，当前任务是修正硬件数值再准备7020新版。没有重新训练/挑选权重，CNN权重SHA仍为07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493。

新增诊断`prepare_cnn_trace.py`（--raw增加卷积原始累加器逐项输出）：`layer_trace`证明输入像素全一致，白/随机图pool1开始差异，零输入pool2开始差异；`layer_trace_raw`三组12587值逐项全通过C/RTL，说明完整累加可观察性改变了综合结果。`audit_cnn_roms.py`核对全部17ROM/26731权重偏置及仿真副本一致。隔离量化函数INLINEoff、ReLU-first改写均不能修复；原乘法fabric和串行channel变体也不能修复。

**有效修正：**MAC局部累加器`ap_int<40> acc[4]`改为`volatile long long acc[4]`，乘积显式`.to_int64()`后累加，保留有符号更新顺序/存储宽度；保守界证明数值仍在signed40内，不改变数学/训练权重。`volatile_acc`三组逐层3179值（像素、pool1、pool2、hidden、logits）全部C/RTL通过。准确机制尚不能细分为native64或volatile单一原因，不应笼统声称已证明某个工具bug。

主源码`real_cnn_kernel.h`已用上述有效修正，生成器`prepare_real_cnn_hls.py`现在默认写新目录 **`E:/FPGA_Enhance_Work/real_digit_training_20261025/cnn_candidate/hls_corrected/`**，旧hls失败工程保留。完整监控核`verify.log` **6帧1586329像素C/RTL全通过**（分类、margin、count、atomicresult、边带及像素）。`rtl_stream_corrected/simulate.log` **5帧123339像素随机背压/自动重启/复位/AXI读分类和margin全部通过**。HLS单核44BRAM18K、15DSP、6391FF、9480LUT，目标100MHz但仍是HLS估计，未替代整机布线检查。

已准备独立整机目录 **`E:/FPGA_Enhance_Work/camera_real_cnn_20261025/`**，脚本`build_board.tcl`导入原verified NN8 BD，加两核fpga.user:hls:real_digit_monitor:1.0，RAW/ENH地址不变43C30000/43C40000。复用已验证RGB桥、原厂XDC和PS配置，不修改旧工程。HLS导出遇2020.2日期Revision溢出，`fix_real_cnn_revision.py`只生成本项目`run_ippack_revision1.tcl`，正运行Vivado重新打包。通过后再启动该新整机build，布局布线时序通过后才能下载。尚未编译新整机位流、未下载/未写SD。

此前`real_digit_cnn_offline_candidate.zip`与candidate_status.json为上一阶段失败候选记录，保持不动；**不能把旧失败包当新版成功硬件**。整机成功后需新包/新状态，包含修正证据。下一步固定图片模式可复用旧image_test.elf（AXI寄存器10/18/20/28/30/38/40/50/60/70兼容、PS相同），但须核对新XSA地址/PSinit与旧一致。只在独立新测试目录发同批33真实图片，使用新CNN整数参考和相同NN8电脑增强参考，不把PC预览叫FPGA回读。板上旧numerical mismatch只有实物逐位核对后才能声称修复。

## 2026-10-25 最新：真实照片重训，离线候选尚未上板

用户要求加强训练以适用于实际场景。本轮不操作硬件、不写SD，旧候选和失败基线保留。数据/训练根目录`E:/FPGA_Enhance_Work/real_digit_training_20261025/`，主要候选在`cnn_candidate/`。完整说明`真实场景训练结果说明.md`由`finish_real_training.py`生成。

下载SVHN训练文件182,040,794字节（HF darcook/DCPV-Artifacts镜像），官方MD5 e26dedcc434d2e4c54c9b2d4a06d8373核对通过。73,257张按每类800张划验证集，共65,257训练/8,000验证；另5,000/500合成空白控制。固定索引在split_indices.npz。没有用SVHN官方test或Wikimedia照片训练/选择权重。亮度、对比度、平移、噪声仅训练增强；预处理与固定照片测试相同，RGB565、整数luma及8x8池化28x28。

先训练784→64→11 MLP，定点测试60.9903%，未选为主要候选。随后独立训练CNN36轮：Conv3x3 1→8/ReLU/MaxPool2、Conv3x3 8→16/ReLU/MaxPool2、784→32ReLU→11，共26,731参数。冻结权重SHA256 **07478560652fdd4c73e6347f8494cdceecd90cda3f62d8705cbb229babc32493**。完整SVHN官方test26,032张电脑定点 **22,170/26,032=85.1644%**，float85.1375%，float/int预测一致99.7388%。旧模型同一输入电脑仅7/26,032（0.02689%）。测试集比较多个候选后不能继续据此调参并宣称全新盲测。

之前已查看33张回归图：新CNN电脑RAW27/33、旧NN8增强电脑参考18/33；其中30个SVHN RAW26/30，3张完整门牌手动ROI仅1/3，说明大图门牌泛化仍弱。全部成功/失败保留csv、预览，不能称新版板上成绩。另冻结后按每类最早10个test索引固定100张诊断：原始照片 RAW84/Gamma81/NN8 61；RGB×1/8合成暗图 RAW65/Gamma75/NN8 85。均为电脑定点参考；人工压暗不是真实夜拍/lux，不筛失败；100张包含已查看过部分SVHN。正常光增强明显退步，下一阶段应正常光旁路/减弱增强，并用真实暗光数据验证/优化；NanoDCE8权重本轮未改。

新HLS内核`real_cnn_kernel.h`显式signed宽乘积，4个输出通道并行复用；配套生成`prepare_real_cnn_hls.py`。C仿真6帧1,586,329像素的分类、margin、帧号/边带/像素与独立Python参考一致，综合成功。单核HLS估计BRAM18K44、DSP15、LUT10845、FF6730，推理88127周期（100MHz换算0.881ms，非实测）。HLS时钟估计7.882ns超过有效预算7.3ns（目标10ns、不确定度2.7ns），有警告，尚未整机布局布线。

**CNN硬件候选RTL协同仿真失败，拒绝下载：**6帧运行完成，第0帧零输入pred都为10但margin C/Python=7804859，RTL=5048887；另外一些帧类别也不同。两个单帧隔离实验（全部乘法改fabric、通道完全串行移除cyclic分区）均复现相同margin差异，因此不是简单归因DSP映射或4路bank/unroll。根因未定位，下一次应优先增加逐层激活/权重ROM数值追踪，不能继续无依据换pragma。Csim通过不能替代RTL/实物。状态`cnn_candidate/candidate_status.json`为OFFLINE_TRAINED_HARDWARE_CANDIDATE_REJECTED_RTL_MISMATCH，细节`hardware_diagnostics.json`、evidence及hls各日志。旧板上数值差异**未证明修复**。

当前板卡仍是旧位流+固定照片app，未下载新版CNN。原SD电脑BOOT和冻结旧digit候选bit哈希不变。下一步先检查候选RTL/整机资源时序及实物数值一致性，再做同批真实图片上板对照，最后才摄像头实拍。不是完整场景自动检测/车牌OCR；空白控制不是任意未知物拒识。

本轮训练/报告已归档`E:/FPGA_Enhance_Work/real_digit_training_20261025/real_digit_cnn_offline_candidate.zip`（2,294,568字节，**离线候选包，不是可下载到板卡的成功版**），包内包括训练源码、整数权重、完整回归及失败硬件证据，排除182MB训练集和巨大HLS工程。完整工程留在原目录。

## 2026-10-25 最新：网络真实照片测试，当前模型不适用

用户指出黑底白字照片过于特殊，要求网上真实照片识别。已下载SVHN cropped test（64275384字节），原站HTTP502/HTTPS EOF后使用HF镜像darcook/DCPV-Artifacts，MD5与torchvision官方eb5a983be6a315427106f1b164d9cef3一致。数据及source_manifest在`E:/FPGA_Enhance_Work/real_scene_test_20261025/`。另从Wikimedia下载3张真实门牌：House number8.JPG（SeppVei/PD）、Hausnummer5inFrankreich（Palauenc05/CC BY-SA4.0）、House number8placeConcorde（Tangopaso/PD），保留完整照片/署名/来源。

**有效测试目录：**`E:/FPGA_Enhance_Work/real_scene_test_scaled_20261025/`。SVHN按每个数字最早3个测试索引固定30张，另3张完整照片人工ROI，共33张；全部原色/背景，无人工压暗、二值化、反色或去背景。SVHN原始32×32明确放大到224×224，3个门牌手动ROI位置在推理前标注；不是完整场景自动定位/车牌OCR。

最初代码用thumbnail未放大小图，数字在224框内过小，那一轮原目录标INVALID_UNSCALED_INPUTS.json、结果作废；修正为显式resize后用2×2高对比探针验证图像内容覆盖ROI，重新准备33张并重新上板，所有有效结果在scaled目录。

**有效板上结果：RAW0/33，ENH0/33**。RAW32张输出背景类10，1张真值9输出6；ENH33张均输出背景10。分类10在这些有数字照片里是失败，不能解释为“没有数字”。电脑参考同样0/33。所有输入FNV校验通过，首张整帧DDR回读逐字节一致，VDMA错误0。没有换模型或权重、没有发真值给板卡、没有写SD。18张在类别或margin上与软件参考不同，之前的数值差异仍未解决。

当前板上留在真实巴黎数字8门牌照片（commons_2_roi），两路均背景类10（屏幕'-'）；不是早先演示8的RAW6/ENH8。说明`真实照片测试说明.md`、预览`真实照片预览.png`、结果`board_batch_33/board_results.csv`和`hardware_test_status.json`。本模型不能通过真实场景验收，不能继续将黑底白字结果当作真实识别能力。应保留失败基线，先解决数值一致性、用独立的真实数字训练数据更换识别器，再在独立真实照片上验收；当前0/33不能证明增强有助识别。

## 2026-10-25 当前最新：固定图片输入模式

用户要求先不用摄像头，改为电脑给开发板图片，已完成并上板。当前板上是独立`image_test.elf`，同一FPGA位流/权重，关闭摄像头S2MM、MM2S停车模式和禁用genlock。程序未初始化摄像头。DDR图像双缓冲0x02000000/0x02119400，每帧1152000字节，mailbox0x03000000；ELF至0x11A500，不重叠。只写未显示缓冲，帧边界切换，等三帧并配对同一帧识别；主机不向板上发送真值或参考预测。

工作及结果目录`E:/FPGA_Enhance_Work/fixed_image_test_20261025/`，归档`E:/FPGA_Enhance_Work/fixed_image_test_20261025_ready.zip`（5,384,879字节）。说明见`使用与结果说明.md`，全部数据及未解决问题见`hardware_test_status.json`和`batch_38/board_results.csv`。38输入均通过板上FNV-1a，首张整帧从DDR读回逐字节一致，VDMA错误0。用户确认“左右都是固定数字8，右侧更亮”。SD未改。

板上30个固定数字（每档0–9各一个）结果：正常光RAW9/10、ENH9/10；合成alpha1/8时RAW1/10、ENH9/10；alpha1/16时RAW0/10、ENH8/10。另有2个demo8、3个空背景、1个颜色对照、2张自然图，共38，不筛失败。当前留在demo8_dim：RAW=6、ENH=8；正常demo8两路均8。这是合成小样本实测，不是摄像头准确率或lux测试。

**尚未解决：**35/38输入的类别或margin与电脑定点参考不一致（RAW类别11例、ENH类别2例）。新C仿真、独立生成RTL仿真（随机停顿2帧及连续4帧1536000像素）与电脑参考一致，生成/打包/缓存RTL及ROM数据相同。实物旁路mode0时两板上核都输出RAW6及相同margin，恢复mode1后为RAW6/ENH8。输入损坏、简单R/B交换或±8像素ROI偏移均未解释问题，综合后数值仍需查。报告全部保留，不可把板上结果替换成软件参考或声称逐位一致。

增强RGB仅送LCD，没有输出回DDR；`pc_reference_previews`是电脑参考PNG，绝不能标成板上图像回读或据此宣称硬件PSNR。恢复摄像头数字识别时执行原候选`camera_nn_digit_candidate_20261023/download_digit_jtag.tcl`；当前不是摄像头模式。运行固定图的启动/发图脚本在新目录，文档含准确命令。

## 2026-10-25 上板状态（更新优先于下方构建时记录）

用户已授权并完成JTAG临时下载。最初两次未发现USB下载器，用户重插后识别到USB VID0403/PID6014、序列号210512180081及XC7Z020/APU。候选原文件校验通过；成功日志包含DIGIT_ALL_THREE_CORES_CONFIGURED、DIGIT_JTAG_START_PASS。

证据目录：`E:/FPGA_Enhance_Work/camera_nn_digit_20261023/hardware_validation_20261025/`。首次12次只读健康采样通过，VDMA错误位0、停机0、识别帧计数停更0。用户确认“画面实时变化，绿色框和 RAW／ENH 都有”。正常光数字8测试，用户确认“RAW=8，ENH不是8”：这一实物样例增强反而影响了识别，不能宣称实物识别优势或统计准确率。随后尝试对数字8回读时JTAG目标不可见，未取得该样例对应寄存器数据，也未复位或写板。SD未写，旧NN8位流和原BOOT.BIN电脑文件哈希未改。

下面的“未下载”描述为10月23日候选归档时状态；冻结候选目录和ZIP保持原样，后续实物状态以本更新和上述证据目录为准。

## 2026-10-23 构建记录

用户要求先准备模型，回来后才下载验证。本目录已完成候选构建，**未接触硬件、未下载、未写SD卡**。

- 候选包：`E:/FPGA_Enhance_Work/camera_nn_digit_candidate_20261023/`，同名ZIP4,694,826字节。
- 原始构建：`E:/FPGA_Enhance_Work/camera_nn_digit_20261023/prj/camera_digit.xpr`。
- 模型/训练/离线评估/HLS/RTL仿真：`E:/FPGA_Enhance_Work/digit_recognition_20261023/`。
- 物理当前仍是此前用户确认有画面且颜色正常的NN8-Cal；恢复包 `E:/FPGA_Enhance_Work/camera_nn8_verified_20261023/`。
- 旧SD的电脑BOOT.BIN仍在 `E:/FPGA_Enhance_Work/camera_nn_sd_20261018/BOOT.BIN`；未改。其冷启动是否成功仍需实际观察。

首版是固定ROI(x480,y112,224×224)里的单个黑底白数字，非完整车牌检测/中文OCR。训练的识别器784→32ReLU→11，共25,483参数；MNIST独立测试95.46%，未见字体120张90.83%，均为电脑结果。

处理链为：已验证摄像头/VDMA/DDR→通道桥→RAW识别器→NanoDCE8-Cal→ENH识别器/文字框→通道桥→LCD。两个识别器用同一权重；捕获ROI在文字叠加之前。ARM只初始化、配对同帧结果和更新显示。NanoDCE8-Cal仍是先前校准初始化，没有成功蒸馏提升的主张。

NN地址0x43C20000；RAW地址0x43C30000；ENH地址0x43C40000。数字结果原子寄存器偏移0x70，位31..4=28位帧号，位3..0=类别0..9/10背景。count已加HLS RESET，独立RTL测试核对了复位后帧号重启。ARM只显示帧号匹配的两路结果，标签有延迟。

实际布线：LUT21820，FF24295，BRAM62，DSP208/220（NN128、RAW40、ENH40）。100MHz，WNS0.229ns、WHS0.015ns、5项bus-skew最小8.886ns。继承原厂PCLK非专用路由例外和缺失外部I/O延时；有Warning/Advisory，无Error/Critical。PS7初始化与已验证NN8逐字节一致；新ELF内存0x100000..0x11A580，不与0x01100000视频缓冲重叠。

C/RTL最终版6帧545946像素；独立RTL自动重启/随机背压/复位5帧123339像素均通过。具体证据在候选包evidence及build_status.json。尚未实测摄像头识别、颜色、帧率、延迟、稳定性和功耗。

离线固定160数字、20空背景、6合成亮度、4方法的1080条记录完整保留，含失败。亮度1：RAW91.875%、NN8 88.125%；1/8：RAW33.75%、Gamma95%、NN8 93.75%；1/16：RAW0.625%、Gamma84.375%、NN8 93.125%。合成RGB系数不是lux，不能推广成实物或完整车牌优势。

包内README有未来JTAG下载和旧版恢复命令。下一次用户回来授权下载时使用该候选包的`download_digit_jtag.tcl`，先检查电源/JTAG/启动开关，然后观察正常光0–9，之后才测试暗光。切勿自动写SD。
