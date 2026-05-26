import cv2
import numpy as np


class Spliter:

    @staticmethod
    def segment_video(input_path, output_path="segment", flow_thresh=5.0):
        """
        基于光流法对视频进行分段切割

        :param output_path: 输出视频路径
        :param input_path: 输入视频路径
        :param flow_thresh: 光流幅值阈值，超过此值认为发生场景切换或剧烈运动
        """
        # 1. 打开视频并获取基础信息
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print("无法打开视频文件")
            return

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 读取第一帧作为基准帧
        ret, prev_frame = cap.read()
        if not ret:
            print("视频首帧读取失败")
            return
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        # 初始化视频写入器和帧计数器
        fourcc = 0x7634706d
        out = cv2.VideoWriter(f"{output_path}_0.mp4", fourcc, fps, (width, height))
        out.write(prev_frame)  # 写入第一帧

        segment_idx = 0
        frame_count = 1

        while True:
            ret, curr_frame = cap.read()
            if not ret: break

            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            # 2. 计算稠密光流 (Farneback算法)
            # 参数可根据实际视频分辨率和运动幅度微调
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, curr_gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0
            )

            # 3. 将笛卡尔坐标转换为极坐标，获取光流的速度（幅值）
            magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

            # 计算整帧光流速度的平均值
            avg_magnitude = np.mean(magnitude)

            # 4. 判断是否达到切割条件
            if avg_magnitude > flow_thresh:
                # 关闭当前的视频文件
                out.release()
                segment_idx += 1
                print(f"检测到关键切割点 (帧 {frame_count})，平均光流速度: {avg_magnitude:.2f}")

                # 创建新的视频文件
                out = cv2.VideoWriter(f"{output_path}_{segment_idx}.mp4", fourcc, fps, (width, height))

            # 5. 写入当前帧并更新基准帧
            out.write(curr_frame)
            prev_gray = curr_gray.copy()
            frame_count += 1

        # 释放所有资源
        cap.release()
        out.release()





