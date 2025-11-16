import { useState, useEffect } from 'react';
import { HelpCircle, Plus, Send, X, Upload } from 'lucide-react';

function App() {
  const [page, setPage] = useState<'welcome' | 'phone' | 'otp' | 'success' | 'home'>('welcome');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [otp, setOtp] = useState(['', '', '', '']);
  const [timeLeft, setTimeLeft] = useState(300);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [verificationStep, setVerificationStep] = useState<'idle' | 'id-card' | 'selfie' | 'waiting' | 'complete'>('idle');
  const [idCardUploads, setIdCardUploads] = useState({ front: false, back: false });
  const [selfieUpload, setSelfieUpload] = useState(false);
  const [isVerified, setIsVerified] = useState(false);
  const [sendMoneyStep, setSendMoneyStep] = useState<'idle' | 'recipient' | 'amount' | 'wallet' | 'loading' | 'transaction-success'>('idle');
  const [recipientInput, setRecipientInput] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [transactions, setTransactions] = useState<Array<{ id: string; amount: string; recipient: string; date: string; cardEndDigits: string }>>([]);

  useEffect(() => {
    if (page !== 'otp') return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(timer);
  }, [page]);

  useEffect(() => {
    if (page === 'home') {
      const timer = setTimeout(() => {
        setShowVerifyModal(true);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [page]);

  const handleOtpChange = (index: number, value: string) => {
    const newOtp = [...otp];
    newOtp[index] = value.slice(-1);
    setOtp(newOtp);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleFileUpload = (type: 'front' | 'back' | 'selfie') => {
    if (type === 'front' || type === 'back') {
      setIdCardUploads(prev => ({ ...prev, [type]: true }));
    } else {
      setSelfieUpload(true);
    }
  };

  const handleStartVerification = () => {
    setShowVerifyModal(false);
    setVerificationStep('id-card');
    setIdCardUploads({ front: false, back: false });
    setSelfieUpload(false);
  };

  const handleIdCardNext = () => {
    if (idCardUploads.front && idCardUploads.back) {
      setVerificationStep('selfie');
    }
  };

  const handleBack = () => {
    if (verificationStep === 'id-card') {
      setVerificationStep('idle');
      setShowVerifyModal(false);
    } else if (verificationStep === 'selfie') {
      setVerificationStep('id-card');
    } else if (verificationStep === 'waiting') {
      setVerificationStep('selfie');
    }
  };

  const handleSelfieNext = () => {
    if (selfieUpload) {
      setVerificationStep('waiting');
    }
  };

  const handleSubmit = () => {
    setVerificationStep('complete');
  };

  const handleBackToHome = () => {
    setVerificationStep('idle');
    setShowVerifyModal(false);
    setIsVerified(true);
  };

  const handleOpenSendMoney = () => {
    setSendMoneyStep('recipient');
    setRecipientInput('');
    setAmountInput('');
    setSelectedPaymentMethod('');
  };

  const handleCloseSendMoney = () => {
    setSendMoneyStep('idle');
    setRecipientInput('');
    setAmountInput('');
    setSelectedPaymentMethod('');
  };

  const handleRecipientNext = () => {
    if (recipientInput.trim()) {
      setSendMoneyStep('amount');
    }
  };

  const handleAmountNext = () => {
    if (parseFloat(amountInput) >= 20 && parseFloat(amountInput) <= 1425) {
      setSendMoneyStep('wallet');
    }
  };

  const handleSelectPaymentMethod = (method: string) => {
    setSelectedPaymentMethod(method);
    if (method === 'google-pay') {
      setIsProcessing(true);
      setTimeout(() => {
        setSendMoneyStep('loading');
        setIsProcessing(false);
        setTimeout(() => {
          setSendMoneyStep('transaction-success');
        }, 3000);
      }, 500);
    }
  };

  const handleSendMoneyBack = () => {
    if (sendMoneyStep === 'amount') {
      setSendMoneyStep('recipient');
    } else if (sendMoneyStep === 'wallet') {
      setSendMoneyStep('amount');
    }
  };

  const handleTransactionComplete = () => {
    if (amountInput && recipientInput) {
      const newTransaction = {
        id: Date.now().toString(),
        amount: amountInput,
        recipient: recipientInput,
        date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
        cardEndDigits: '1436'
      };
      setTransactions([newTransaction, ...transactions]);
    }
    setSendMoneyStep('idle');
    setRecipientInput('');
    setAmountInput('');
    setSelectedPaymentMethod('');
  };

  return (
    <div className="min-h-screen bg-[#1a1a1a]">
      {page === 'welcome' && (
        <div className="min-h-screen flex flex-col items-center justify-between px-6 py-8 animate-fade-in">
          <div className="w-full max-w-md flex flex-col items-center flex-1">
            <div className="flex items-center justify-center space-x-2 pt-2">
              <span className="text-xl font-medium tracking-tight text-white">Ubique Pay</span>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="relative mb-12 animate-bounce-subtle">
                <div className="w-32 h-32 rounded-full bg-[#5bffb4] flex items-center justify-center">
                  <div className="text-4xl">
                    <div className="flex flex-col items-center justify-center space-y-1">
                      <div className="flex space-x-1.5">
                        <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                        <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                      </div>
                      <div className="w-8 h-1 bg-[#1a1a1a] rounded-full mt-2"></div>
                    </div>
                  </div>
                </div>
                <div className="absolute -top-2 -right-2 w-8 h-8 bg-[#5bffb4] rounded-full transform rotate-45"></div>
              </div>

              <h1 className="text-4xl font-medium text-white text-center mb-2">
                Send money to
              </h1>
              <h2 className="text-4xl font-medium text-[#5bffb4] text-center">
                anyone, anywhere.
              </h2>
            </div>
          </div>

          <button
            onClick={() => setPage('phone')}
            className="w-full max-w-md bg-[#5bffb4] text-[#1a1a1a] text-lg font-medium py-5 rounded-full hover:bg-[#4ee9a3] transition-colors"
          >
            Start
          </button>
        </div>
      )}

      {page === 'phone' && (
        <div className="min-h-screen flex flex-col items-center justify-between px-6 py-8 animate-slide-up">
          <div className="w-full max-w-md flex flex-col items-center flex-1">
            <div className="flex items-center justify-between w-full mb-8">
              <button
                onClick={() => setPage('welcome')}
                className="text-white hover:text-gray-400 transition-colors"
              >
                ←
              </button>
              <span className="text-xl font-medium tracking-tight text-white">Ubique Pay</span>
              <HelpCircle className="w-6 h-6 text-gray-600 hover:text-gray-400 transition-colors cursor-pointer" />
            </div>

            <div className="flex-1 flex flex-col items-start w-full justify-center">
              <h1 className="text-4xl font-medium text-[#5bffb4] mb-8 animate-slide-in-left">
                Add phone number
              </h1>

              <div className="w-full">
                <div className="flex items-center space-x-2 mb-3 animate-slide-in-left" style={{ animationDelay: '100ms' }}>
                  <span className="text-2xl font-medium text-white">+994</span>
                  <input
                    type="text"
                    placeholder="10 123 45 67"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value.replace(/\D/g, ''))}
                    className="text-2xl font-medium bg-transparent text-gray-500 placeholder-gray-600 outline-none flex-1"
                  />
                </div>
                <div className="w-full h-px bg-gradient-to-r from-white to-transparent"></div>
              </div>
            </div>
          </div>

          <div className="w-full max-w-md flex gap-3">
            <button className="flex-1 border border-gray-600 text-white text-lg font-medium py-4 rounded-full hover:border-gray-400 transition-colors">
              Learn more
            </button>
            <button
              onClick={() => setPage('otp')}
              className="flex-1 bg-[#5bffb4] text-[#1a1a1a] text-lg font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors"
            >
              Send code
            </button>
          </div>
        </div>
      )}

      {page === 'otp' && (
        <div className="min-h-screen flex flex-col items-center justify-between px-6 py-8 animate-slide-up">
          <div className="w-full max-w-md flex flex-col items-center flex-1">
            <div className="flex items-center justify-between w-full mb-8">
              <button
                onClick={() => setPage('phone')}
                className="text-white hover:text-gray-400 transition-colors"
              >
                ←
              </button>
              <span className="text-xl font-medium tracking-tight text-white">Ubique Pay</span>
              <HelpCircle className="w-6 h-6 text-gray-600 hover:text-gray-400 transition-colors cursor-pointer" />
            </div>

            <div className="flex-1 flex flex-col items-start w-full justify-center">
              <h1 className="text-4xl font-medium text-[#5bffb4] mb-2 animate-slide-in-left">
                Enter OTP code
              </h1>
              <p className="text-gray-400 mb-8 animate-slide-in-left" style={{ animationDelay: '50ms' }}>
                <span className="text-white">{formatTime(timeLeft)}</span> time.{' '}
                <button className="text-[#5bffb4] hover:text-[#4ee9a3] transition-colors underline">
                  Resend it
                </button>
              </p>

              <div className="flex gap-4 w-[0.25] animate-slide-in-left" style={{ animationDelay: '100ms' }}>
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    type="text"
                    inputMode="numeric"
                    maxLength="1"
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value)}
                    className="flex-1 aspect-square border border-gray-600 rounded-lg text-3xl font-medium text-center text-white bg-transparent placeholder-gray-700 outline-none hover:border-gray-400 focus:border-[#5bffb4] transition-colors w-[50px] h-[50px]"
                  />
                ))}
              </div>
            </div>
          </div>

          <button
            onClick={() => setPage('success')}
            className="w-full max-w-md bg-[#5bffb4] text-[#1a1a1a] text-lg font-medium py-5 rounded-full hover:bg-[#4ee9a3] transition-colors"
          >
            Create Account
          </button>
        </div>
      )}

      {page === 'success' && (
        <div className="min-h-screen flex flex-col items-center justify-between px-6 py-8 animate-fade-in">
          <div className="w-full max-w-md flex flex-col items-center flex-1">
            <div className="flex items-center justify-center space-x-2 pt-2">
              <span className="text-xl font-medium tracking-tight text-white">Ubique Pay</span>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="mb-8 animate-scale-in">
                <div className="w-40 h-40 rounded-full bg-[#5bffb4] flex items-center justify-center relative overflow-hidden">
                  <div className="absolute top-6 right-8 w-6 h-6 bg-[#1a1a1a] rounded-full opacity-80"></div>
                  <div className="text-6xl font-bold text-[#1a1a1a]">
                    <div className="flex flex-col items-center justify-center">
                      <div className="flex space-x-2">
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                      </div>
                      <div className="w-4 h-1 bg-[#1a1a1a] rounded-full mt-3"></div>
                    </div>
                  </div>
                </div>
              </div>

              <h1 className="text-4xl font-medium text-[#5bffb4] text-center animate-slide-in-left">
                Successfully created
              </h1>
              <h2 className="text-4xl font-medium text-[#5bffb4] text-center animate-slide-in-left" style={{ animationDelay: '100ms' }}>
                your account!
              </h2>
            </div>
          </div>

          <button
            onClick={() => setPage('home')}
            className="w-full max-w-md bg-[#5bffb4] text-[#1a1a1a] text-lg font-medium py-5 rounded-full hover:bg-[#4ee9a3] transition-colors"
          >
            Start
          </button>
        </div>
      )}

      {page === 'home' && (
        <div className="min-h-screen bg-[#1a1a1a] flex flex-col px-6 py-8 animate-slide-up">
          <div className="w-full max-w-md mx-auto flex flex-col">
            {verificationStep === 'idle' && (
              <>
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-[#5bffb4] flex items-center justify-center flex-shrink-0 animate-scale-in">
                      <div className="flex flex-col items-center justify-center">
                        <div className="flex space-x-1">
                          <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                          <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                        </div>
                        <div className="w-3 h-0.5 bg-[#1a1a1a] rounded-full mt-1"></div>
                      </div>
                    </div>
                    <div className="animate-slide-in-left">
                      <div className="flex items-center gap-2">
                        <p className="text-white font-medium">Diana Rossel</p>
                        {isVerified && (
                          <div className="w-5 h-5 rounded-full bg-[#5bffb4] flex items-center justify-center flex-shrink-0">
                            <span className="text-[#1a1a1a] text-xs font-bold">✓</span>
                          </div>
                        )}
                      </div>
                      <p className="text-gray-400 text-sm">+1 345 678 901</p>
                    </div>
                  </div>
                  <HelpCircle className="w-6 h-6 text-gray-600 hover:text-gray-400 transition-colors cursor-pointer" />
                </div>

                <div className="bg-gradient-to-br from-[#5bffb4] to-[#4ee9a3] rounded-2xl p-6 mb-6 animate-slide-in-left" style={{ animationDelay: '100ms' }}>
                  <p className="text-[#1a1a1a] text-sm font-medium opacity-80 mb-2">Ubique Pay</p>
                  <div className="h-20 flex items-end">
                    <p className="text-[#1a1a1a] text-lg font-medium">Recent card number</p>
                  </div>
                </div>

                <div className="flex gap-3 mb-8 animate-slide-in-left" style={{ animationDelay: '150ms' }}>
                  <button className="flex-1 border border-gray-700 text-white font-medium py-4 rounded-full hover:border-gray-500 transition-colors flex items-center justify-center gap-2">
                    <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    Pay
                  </button>
                  <button 
                    onClick={handleOpenSendMoney}
                    className="flex-1 bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors flex items-center justify-center gap-2"
                  >
                    <Send className="w-5 h-5" />
                    Send Money
                  </button>
                </div>

                {!showVerifyModal && !isVerified && (
                  <div className="bg-[#262626] rounded-2xl p-6 mb-8 animate-slide-in-left" style={{ animationDelay: '175ms' }}>
                    <div className="flex gap-4 mb-6">
                      <div className="w-16 h-16 rounded-full bg-[#5bffb4] flex items-center justify-center flex-shrink-0">
                        <div className="flex flex-col items-center justify-center">
                          <div className="flex space-x-1.5">
                            <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                            <div className="w-1.5 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                          </div>
                          <div className="w-4 h-0.5 bg-[#1a1a1a] rounded-full mt-1"></div>
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-white font-medium text-lg mb-1">Verify your account</h3>
                        <p className="text-gray-400 text-sm leading-relaxed">
                          After completing verification, you can increase your limits. At the moment, your transfer limit is <span className="text-[#5bffb4]">250 USD</span>.
                        </p>
                      </div>
                    </div>
                    <button onClick={handleStartVerification} className="w-full bg-[#5bffb4] text-[#1a1a1a] font-medium py-3 rounded-full hover:bg-[#4ee9a3] transition-colors">
                      Verify
                    </button>
                  </div>
                )}

                <div className="flex-1 animate-slide-in-left" style={{ animationDelay: '200ms' }}>
                  <div className="mb-4">
                    <p className="text-white font-medium mb-2">Recent Transactions</p>
                    <div className="w-16 h-1 bg-[#5bffb4] rounded-full"></div>
                  </div>

                  {transactions.length > 0 ? (
                    <div className="space-y-4">
                      {transactions.map((transaction) => (
                        <div key={transaction.id} className="flex items-center justify-between p-4 bg-[#262626] rounded-xl hover:bg-[#2d2d2d] transition-colors">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-[#5bffb4] flex items-center justify-center flex-shrink-0">
                              <Send className="w-5 h-5 text-[#1a1a1a]" />
                            </div>
                            <div>
                              <p className="text-white font-medium text-sm">To {transaction.recipient}</p>
                              <p className="text-gray-400 text-xs">{transaction.date}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-white font-medium">-${transaction.amount}</p>
                            <p className="text-gray-400 text-xs">Card ...{transaction.cardEndDigits}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
                        <div className="flex flex-col items-center justify-center">
                          <div className="flex space-x-1">
                            <div className="w-1.5 h-1.5 bg-gray-600 rounded-full"></div>
                            <div className="w-1.5 h-1.5 bg-gray-600 rounded-full"></div>
                          </div>
                          <div className="w-3 h-0.5 bg-gray-600 rounded-full mt-1"></div>
                        </div>
                      </div>
                      <p className="text-gray-400">You have no transactions</p>
                    </div>
                  )}
                </div>
              </>
            )}

            {verificationStep === 'id-card' && (
              <div className="flex flex-col h-screen">
                <div className="flex items-center justify-between mb-8">
                  <button
                    onClick={handleBack}
                    className="text-white hover:text-gray-400 transition-colors"
                  >
                    ←
                  </button>
                  <span className="text-xl font-medium text-white">Verification</span>
                  <div className="w-6"></div>
                </div>

                <div className="flex-1 flex flex-col justify-center">
                  <h1 className="text-4xl font-medium text-[#5bffb4] mb-4 leading-tight">
                    Upload clear photos of your ID card.
                  </h1>

                  <div className="flex gap-4 mt-8">
                    <button
                      onClick={() => handleFileUpload('front')}
                      className={`flex-1 border-2 border-dashed rounded-2xl py-8 px-4 transition-all flex flex-col items-center justify-center gap-3 ${
                        idCardUploads.front
                          ? 'border-[#5bffb4] bg-[#5bffb4]/10'
                          : 'border-gray-600 hover:border-gray-400'
                      }`}
                    >
                      <Plus className="w-6 h-6 text-gray-400" />
                      <span className="text-white font-medium">
                        {idCardUploads.front ? '✓ Front side' : 'Front side'}
                      </span>
                    </button>
                    <button
                      onClick={() => handleFileUpload('back')}
                      className={`flex-1 border-2 border-dashed rounded-2xl py-8 px-4 transition-all flex flex-col items-center justify-center gap-3 ${
                        idCardUploads.back
                          ? 'border-[#5bffb4] bg-[#5bffb4]/10'
                          : 'border-gray-600 hover:border-gray-400'
                      }`}
                    >
                      <Plus className="w-6 h-6 text-gray-400" />
                      <span className="text-white font-medium">
                        {idCardUploads.back ? '✓ Back side' : 'Back side'}
                      </span>
                    </button>
                  </div>
                </div>

                <div className="flex gap-3 mt-8">
                  <button
                    onClick={handleBack}
                    className="flex-1 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleIdCardNext}
                    disabled={!idCardUploads.front || !idCardUploads.back}
                    className="flex-1 bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {verificationStep === 'selfie' && (
              <div className="flex flex-col h-screen">
                <div className="flex items-center justify-between mb-8">
                  <button
                    onClick={handleBack}
                    className="text-white hover:text-gray-400 transition-colors"
                  >
                    ←
                  </button>
                  <span className="text-xl font-medium text-white">Verification</span>
                  <div className="w-6"></div>
                </div>

                <div className="flex-1 flex flex-col justify-center">
                  <h1 className="text-4xl font-medium text-[#5bffb4] mb-8 leading-tight">
                    Upload a quick selfie for verification.
                  </h1>

                  <button
                    onClick={() => handleFileUpload('selfie')}
                    className={`border-2 border-dashed rounded-2xl py-16 px-6 transition-all flex flex-col items-center justify-center gap-4 ${
                      selfieUpload
                        ? 'border-[#5bffb4] bg-[#5bffb4]/10'
                        : 'border-gray-600 hover:border-gray-400'
                    }`}
                  >
                    <Plus className="w-8 h-8 text-gray-400" />
                    <span className="text-white font-medium text-lg">
                      {selfieUpload ? '✓ Upload selfie' : 'Upload selfie'}
                    </span>
                  </button>
                </div>

                <div className="flex gap-3 mt-8">
                  <button
                    onClick={handleBack}
                    className="flex-1 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleSelfieNext}
                    disabled={!selfieUpload}
                    className="flex-1 bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {verificationStep === 'waiting' && (
              <div className="flex flex-col h-screen items-center justify-between py-8">
                <div className="flex items-center justify-between w-full mb-8">
                  <span className="text-xl font-medium text-white">Verification</span>
                  <div className="w-6"></div>
                </div>

                <div className="flex-1 flex flex-col items-center justify-center">
                  <div className="mb-8 animate-scale-in">
                    <div className="w-40 h-40 rounded-full bg-[#5bffb4] flex items-center justify-center">
                      <div className="flex flex-col items-center justify-center">
                        <div className="flex space-x-2 mb-2">
                          <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                          <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                        </div>
                        <div className="w-6 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                      </div>
                    </div>
                  </div>

                  <h1 className="text-4xl font-medium text-[#5bffb4] text-center animate-slide-in-left">
                    Waiting for verification
                  </h1>
                </div>

                <button
                  onClick={handleSubmit}
                  className="w-full bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors"
                >
                  Submit
                </button>
              </div>
            )}

            {verificationStep === 'complete' && (
              <div className="flex flex-col h-screen items-center justify-center">
                <div className="mb-8 animate-scale-in">
                  <div className="w-40 h-40 rounded-full bg-[#5bffb4] flex items-center justify-center">
                    <div className="flex flex-col items-center justify-center">
                      <div className="flex space-x-2 mb-2">
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                      </div>
                      <div className="w-6 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                    </div>
                  </div>
                </div>

                <h1 className="text-4xl font-medium text-[#5bffb4] text-center mb-4">
                  Verification successful!
                </h1>
                <p className="text-gray-400 text-center mb-8">
                  Your transfer limit has been increased to <span className="text-[#5bffb4]">5,000 USD</span>
                </p>

                <button
                  onClick={handleBackToHome}
                  className="w-full max-w-xs bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors"
                >
                  Back to Home
                </button>
              </div>
            )}

            {sendMoneyStep === 'recipient' && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-end justify-center px-6 z-50 animate-fade-in">
                <div className="bg-[#1a1a1a] rounded-t-3xl p-8 max-w-md w-full animate-slide-up relative max-h-[90vh] overflow-y-auto">
                  <div className="flex items-center justify-between mb-8">
                    <button
                      onClick={handleCloseSendMoney}
                      className="text-white hover:text-gray-400 transition-colors"
                    >
                      ←
                    </button>
                    <span className="text-xl font-medium text-white">Send Money</span>
                    <div className="w-6"></div>
                  </div>

                  <div className="mb-8">
                    <h2 className="text-3xl font-medium text-[#5bffb4] mb-2">
                      Enter recipient's card
                    </h2>
                    <p className="text-gray-400 text-sm">
                      or use a Telegram ID/username instead.
                    </p>
                  </div>

                  <div className="mb-8">
                    <input
                      type="text"
                      placeholder="Enter card number or Telegram ID"
                      value={recipientInput}
                      onChange={(e) => setRecipientInput(e.target.value)}
                      className="w-full bg-transparent text-white placeholder-gray-600 outline-none text-lg pb-4 border-b border-gray-600 focus:border-[#5bffb4] transition-colors"
                      autoFocus
                    />
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={handleCloseSendMoney}
                      className="flex-1 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleRecipientNext}
                      disabled={!recipientInput.trim()}
                      className="flex-1 bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                </div>
              </div>
            )}

            {sendMoneyStep === 'amount' && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-end justify-center px-6 z-50 animate-fade-in">
                <div className="bg-[#1a1a1a] rounded-t-3xl p-8 max-w-md w-full animate-slide-up relative max-h-[90vh] overflow-y-auto">
                  <div className="flex items-center justify-between mb-8">
                    <button
                      onClick={handleSendMoneyBack}
                      className="text-white hover:text-gray-400 transition-colors"
                    >
                      ←
                    </button>
                    <span className="text-xl font-medium text-white">Send Money</span>
                    <div className="w-6"></div>
                  </div>

                  <div className="mb-8">
                    <h2 className="text-3xl font-medium text-[#5bffb4] mb-2">
                      Enter amount
                    </h2>
                    <p className="text-gray-400 text-sm">
                      Minimum amount: 20$<br />Maximum amount: 1425$
                    </p>
                  </div>

                  <div className="mb-8">
                    <input
                      type="number"
                      placeholder="0"
                      value={amountInput}
                      onChange={(e) => setAmountInput(e.target.value)}
                      className="w-full bg-transparent text-white placeholder-gray-600 outline-none text-lg pb-4 border-b border-gray-600 focus:border-[#5bffb4] transition-colors"
                      autoFocus
                    />
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={handleSendMoneyBack}
                      className="flex-1 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleAmountNext}
                      disabled={!parseFloat(amountInput) || parseFloat(amountInput) < 20 || parseFloat(amountInput) > 1425}
                      className="flex-1 bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Send
                    </button>
                  </div>
                </div>
              </div>
            )}

            {sendMoneyStep === 'wallet' && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-end justify-center px-6 z-50 animate-fade-in">
                <div className="bg-[#1a1a1a] rounded-t-3xl p-8 max-w-md w-full animate-slide-up relative max-h-[90vh] overflow-y-auto">
                  <div className="flex items-center justify-between mb-8">
                    <button
                      onClick={handleSendMoneyBack}
                      className="text-white hover:text-gray-400 transition-colors"
                    >
                      ←
                    </button>
                    <span className="text-xl font-medium text-white">Add card</span>
                    <div className="w-6"></div>
                  </div>

                  <div className="mb-8">
                    <h2 className="text-3xl font-medium text-[#5bffb4] mb-6">
                      Connect wallet
                    </h2>
                  </div>

                  <div className="flex flex-col gap-4 mb-6">
                    <button
                      onClick={() => handleSelectPaymentMethod('apple-pay')}
                      className="flex items-center justify-center gap-3 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                    >
                      <span className="text-xl">🍎</span>
                      Pay
                    </button>

                    <button
                      onClick={() => handleSelectPaymentMethod('google-pay')}
                      className="flex items-center justify-center gap-3 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                    >
                      <div className="w-5 h-5 flex items-center justify-center">
                        <svg viewBox="0 0 24 24" className="w-full h-full">
                          <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="14" fill="currentColor" className="font-bold">G</text>
                        </svg>
                      </div>
                      Pay
                    </button>
                  </div>

                  <div className="flex items-center gap-4 mb-6">
                    <div className="flex-1 h-px bg-gray-600"></div>
                    <span className="text-gray-400 text-sm">or</span>
                    <div className="flex-1 h-px bg-gray-600"></div>
                  </div>

                  <button
                    className="w-full flex items-center justify-center gap-2 border border-gray-600 text-white font-medium py-4 rounded-full hover:border-gray-400 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                    With debit/credit card
                  </button>
                </div>
              </div>
            )}

            {sendMoneyStep === 'loading' && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center px-6 z-50 animate-fade-in">
                <div className="flex flex-col items-center justify-center">
                  <div className="w-40 h-40 rounded-full bg-[#5bffb4] flex items-center justify-center relative mb-8 animate-scale-in">
                    <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[#5bffb4] animate-spin"></div>
                    <div className="flex flex-col items-center justify-center">
                      <div className="flex space-x-2 mb-2">
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                        <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                      </div>
                      <div className="w-6 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                    </div>
                  </div>
                  <p className="text-white text-lg font-medium">Processing payment...</p>
                </div>
              </div>
            )}

            {sendMoneyStep === 'transaction-success' && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-end justify-center px-6 z-50 animate-fade-in">
                <div className="bg-[#1a1a1a] rounded-t-3xl p-8 max-w-md w-full animate-slide-up relative max-h-[90vh] overflow-y-auto">
                  <div className="flex flex-col items-center justify-center py-8">
                    <div className="mb-8 animate-scale-in">
                      <div className="w-40 h-40 rounded-full bg-[#5bffb4] flex items-center justify-center">
                        <div className="flex flex-col items-center justify-center">
                          <div className="flex space-x-2 mb-2">
                            <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                            <div className="w-2 h-2 bg-[#1a1a1a] rounded-full"></div>
                          </div>
                          <div className="w-6 h-1.5 bg-[#1a1a1a] rounded-full"></div>
                        </div>
                      </div>
                    </div>

                    <h1 className="text-3xl font-medium text-[#5bffb4] text-center mb-2 animate-slide-in-left">
                      Send successful!
                    </h1>
                    <p className="text-gray-400 text-center mb-8 animate-slide-in-left" style={{ animationDelay: '100ms' }}>
                      ${amountInput} sent to {recipientInput}
                    </p>

                    <button
                      onClick={handleTransactionComplete}
                      className="w-full bg-[#5bffb4] text-[#1a1a1a] font-medium py-4 rounded-full hover:bg-[#4ee9a3] transition-colors"
                    >
                      Go to home
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slide-up {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slide-in-left {
          from { opacity: 0; transform: translateX(-20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes bounce-subtle {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes scale-in {
          from { opacity: 0; transform: scale(0.8); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .animate-fade-in { animation: fade-in 0.5s ease-out; }
        .animate-slide-up { animation: slide-up 0.4s ease-out; }
        .animate-slide-in-left { animation: slide-in-left 0.5s ease-out; }
        .animate-bounce-subtle { animation: bounce-subtle 3s ease-in-out infinite; }
        .animate-scale-in { animation: scale-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}

export default App;
