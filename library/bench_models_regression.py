import numpy as np  # type: ignore
import torch  # type: ignore
from torch.utils.tensorboard import SummaryWriter  # type: ignore

from . import common_preprocessing
from .loggers import LearningLogStorer
from .models_regression import DenseNet


class BenchModelRegressionBase:
    def __init__(self, model, learning_rate):
        # self.input_size = len(self.selected_channels)
        self.model = model
        if torch.cuda.is_available():
            self.model = self.model.cuda()
        self.create_optimizer(learning_rate)
        self.create_logger()

    def create_logger(self):
        self.logger = LearningLogStorer(
            SummaryWriter(comment=f"{str(self.__class__.__name__)}")
        )

    def create_optimizer(self, learning_rate):
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=learning_rate
        )


class SimpleNetBase(BenchModelRegressionBase):
    def init(self):
        pass


class SimpleNetMelsBase(SimpleNetBase):
    pass


class SimpleNetMels40Base(SimpleNetMelsBase):
    N_MELS = 40
    F_MAX = 2000
    OUTPUT_SIZE = N_MELS


class SimpleNetMels80Base(SimpleNetMelsBase):
    N_MELS = 80
    F_MAX = 8000
    OUTPUT_SIZE = N_MELS


class SimpleNetCausalMels40Base(SimpleNetMels40Base):
    LAG_BACKWARD = 1000
    LAG_FORWARD = 0


class SimpleNetLpcsBase(SimpleNetBase):
    def preprocess_sound(self, sound, sampling_rate, ecog_size):
        assert self.patient["sampling_rate"] == sampling_rate
        return common_preprocessing.classic_lpc_pipeline(
            sound,
            self.patient["sampling_rate"],
            self.downsampling_coef,
            ecog_size,
            self.N_LPCS,
        )

    def detect_voice(self, y_batch):
        return np.sum(np.abs(y_batch) > 1.5, axis=1) > int(self.N_LPCS * 0.3)


class SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__10LPCS(
    SimpleNetLpcsBase
):
    N_LPCS = 10
    LAG_BACKWARD = 1000
    LAG_FORWARD = 0
    OUTPUT_SIZE = N_LPCS

    SELECTED_CHANNELS = None


class SimpleNetBase_WithLSTM__CNANNELS_8_16__LAG_1000_0__10LPCS(
    SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__10LPCS
):
    SELECTED_CHANNELS = list(range(8, 16))


class SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_1000_0__10LPCS(
    SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__10LPCS
):
    SELECTED_CHANNELS = list(range(6, 12))


class SimpleNetMfccsBase(SimpleNetBase):
    def preprocess_sound(self, sound, sampling_rate, ecog_size):
        assert self.patient["sampling_rate"] == sampling_rate
        return common_preprocessing.classic_mfcc_pipeline(
            sound,
            self.patient["sampling_rate"],
            self.downsampling_coef,
            ecog_size,
            self.N_MFCC,
        )

    def detect_voice(self, y_batch):
        return True


class SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__40MFCCS(
    SimpleNetMfccsBase
):
    N_MFCC = 40
    LAG_BACKWARD = 1000
    LAG_FORWARD = 0
    OUTPUT_SIZE = N_MFCC

    SELECTED_CHANNELS = None


class SimpleNetBase_WithLSTM__CNANNELS_8_16__LAG_1000_0__40MFCCS(
    SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__40MFCCS
):
    SELECTED_CHANNELS = list(range(8, 16))


class SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_1000_0__40MFCCS(
    SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__40MFCCS
):
    SELECTED_CHANNELS = list(range(6, 12))


# class SimpleNetBase_WithLSTM__CNANNELS_6_11__LAG_1000_0__40MELS(SimpleNetMels40Base):
#     LAG_BACKWARD = 1000
#     LAG_FORWARD = 0

#     SELECTED_CHANNELS = [6, 7, 8, 9, 10, 11]


class SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_0__40MELS(
    SimpleNetMels40Base
):
    LAG_BACKWARD = 1000
    LAG_FORWARD = 0

    SELECTED_CHANNELS = None


class SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_1000_1000__40MELS(
    SimpleNetMels40Base
):
    LAG_BACKWARD = 1000
    LAG_FORWARD = 1000

    SELECTED_CHANNELS = None


class SimpleNetBase_WithLSTM__CNANNELS_ALL__LAG_0_1000__40MELS(
    SimpleNetMels40Base
):
    LAG_BACKWARD = 0
    LAG_FORWARD = 1000

    SELECTED_CHANNELS = None


# Ivanova electrodes


class SimpleNetBase_WithLSTM__CNANNELS_0_8__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(0, 8))


class SimpleNetBase_WithLSTM__CNANNELS_8_16__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(8, 16))


class SimpleNetBase_WithLSTM__CNANNELS_16_24__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(16, 24))


class SimpleNetBase_WithLSTM__CNANNELS_24_30__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(24, 30))


class SimpleNetBase_WithLSTM__CNANNELS_30_36__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(30, 36))


class SimpleNetBase_WithLSTM__CNANNELS_36_42__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(36, 42))


##


class SimpleNetBase_WithLSTM__CNANNELS_8_16_24_30__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(8, 16)) + list(range(24, 30))


class SimpleNetBase_WithLSTM__CNANNELS_8_16__LAG_1000_1000__40MELS(
    SimpleNetMels40Base
):
    SELECTED_CHANNELS = list(range(8, 16))
    LAG_BACKWARD = 1000
    LAG_FORWARD = 1000


class SimpleNetBase_WithLSTM__CNANNELS_8_16__LAG_0_1000__40MELS(
    SimpleNetMels40Base
):
    SELECTED_CHANNELS = list(range(8, 16))
    LAG_BACKWARD = 0
    LAG_FORWARD = 1000


# Procenco electrodes


class SimpleNetBase_WithLSTM__CNANNELS_0_6__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(0, 6))


class SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(6, 12))


class SimpleNetBase_WithLSTM__CNANNELS_MEG__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(306))


class SimpleNetBase_WithLSTM__CNANNELS_12_18__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(12, 18))


class SimpleNetBase_WithLSTM__CNANNELS_18_24__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(18, 24))


class SimpleNetBase_WithLSTM__CNANNELS_24_30__LAG_1000_0__40MELS(
    SimpleNetCausalMels40Base
):
    SELECTED_CHANNELS = list(range(24, 30))


class SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_1000_1000__40MELS(
    SimpleNetMels40Base
):
    SELECTED_CHANNELS = list(range(6, 12))
    LAG_BACKWARD = 1000
    LAG_FORWARD = 1000


class SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_0_1000__40MELS(
    SimpleNetMels40Base
):
    SELECTED_CHANNELS = list(range(6, 12))
    LAG_BACKWARD = 0
    LAG_FORWARD = 1000


class DenseNet_WithLSTM__CNANNELS_6_12__LAG_1000_0__40MELS(
    SimpleNetBase_WithLSTM__CNANNELS_6_12__LAG_1000_0__40MELS
):
    def init(self):
        self.model = DenseNet(
            self.input_size,
            self.OUTPUT_SIZE,
            self.LAG_BACKWARD,
            self.LAG_FORWARD,
        )
        if torch.cuda.is_available():
            self.model = self.model.cuda()


############################################

# class LargeNetBase(SimpleNetBase):
#     def init(self):
#         ecog_frame = 96
#         ecog_stride = 24
#         self.model = Encoder(ecog_frame + self.LAG_BACKWARD + self.LAG_FORWARD, ecog_stride).cuda()


# class LargeNetMelsBase(LargeNetBase, SimpleNetMelsBase):
#     pass

# class LargeNet__CNANNELS_6_11__LAG_1500_1500__80MELS(LargeNetMelsBase):
#     LAG_BACKWARD = 1500
#     LAG_FORWARD = 1500

#     SELECTED_CHANNELS = [6, 7, 8, 9, 10, 11]
#     INPUT_SIZE = len(SELECTED_CHANNELS)
